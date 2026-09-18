import json
import re
from dataclasses import dataclass

from app.ai.providers.base import TextGenerationProvider
from app.modules.writing.domain.entities import Message
from app.modules.writing.domain.enums import MemoryRecordType, MessageDirection
from app.modules.writing.domain.exceptions import MemoryExtractionError

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

MAX_EXTRACTED_MEMORIES = 3
"""Persistent Brain v2 (Decisions 1+2, unified): one extraction pass may surface more than one
durable, worth-remembering fact - a methodological decision AND a terminology definition AND an
observable style trait, for instance. Bounded to a small fixed number so one pass can never
produce runaway memory growth ("avoid hallucinated learning").
"""


@dataclass(frozen=True)
class ExtractedMemory:
    """Semantic data only - mirrors `style_extraction.ExtractedCharacteristic`'s own
    discipline: the provider returns this and nothing else, never a persistence identifier.
    The application layer alone decides `agent_id`, provenance, and how it is persisted.
    """

    record_type: MemoryRecordType
    content: str
    rationale: str | None


def parse_memory_extraction_response(raw_response: str) -> list[ExtractedMemory]:
    """Never coerces an invalid value into a guessed one (mirrors
    `style_extraction.parse_style_extraction_response`'s own discipline) - a malformed or
    unrecognized response raises rather than silently falling back to `other`, so a bad
    extraction is retried (via the Work Item's own bounded retry) rather than persisted as a
    low-quality guess. An empty `memories` list is valid (the model may genuinely find nothing
    worth remembering) and returns an empty list, not an error.
    """
    cleaned = _CODE_FENCE.sub("", raw_response).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise MemoryExtractionError(reason="provider response was not valid JSON") from exc

    if not isinstance(payload, dict):
        raise MemoryExtractionError(reason="provider response was not a JSON object")

    raw_memories = payload.get("memories")
    if not isinstance(raw_memories, list):
        raise MemoryExtractionError(reason="response did not contain a 'memories' list")
    if len(raw_memories) > MAX_EXTRACTED_MEMORIES:
        raise MemoryExtractionError(reason=f"response returned more than {MAX_EXTRACTED_MEMORIES} memories")

    extracted: list[ExtractedMemory] = []
    for item in raw_memories:
        if not isinstance(item, dict):
            raise MemoryExtractionError(reason="a memory entry was not a JSON object")

        try:
            record_type = MemoryRecordType(item.get("record_type"))
        except ValueError as exc:
            raise MemoryExtractionError(
                reason=f"record_type {item.get('record_type')!r} is not one of the approved values"
            ) from exc

        content = item.get("content")
        if not content or not str(content).strip():
            raise MemoryExtractionError(reason="content was missing or empty")

        rationale = item.get("rationale")
        rationale = str(rationale).strip() if rationale and str(rationale).strip() else None

        extracted.append(ExtractedMemory(record_type=record_type, content=str(content).strip(), rationale=rationale))

    return extracted


MEMORY_EXTRACTION_TRIGGER_COUNT = 20
"""Memory's only automatic trigger, now that the Drafts/Review pipeline (Persistent Brain
Decision 4's original trigger) has been removed entirely - the user only ever wants chat
replies, not a separate generate-then-review document workflow (recorded in
docs/Project_Writing_Implementation_Plan.md). Mirrors `conversation_summarization.
CONVERSATION_SUMMARY_TRIGGER_COUNT`'s own periodic-trigger shape: extracts memory from the
conversation every this-many real messages, bounding API usage instead of calling the
provider on every single message.
"""

MAX_TRANSCRIPT_MESSAGE_CHARACTERS = 500
"""Bounds each message's contribution to the extraction prompt - mirrors
`conversation_summarization.MAX_SUMMARIZED_MESSAGE_CHARACTERS`'s own reasoning."""

_TRANSCRIPT_LABELS = {
    MessageDirection.USER_REQUEST: "User",
    MessageDirection.SYSTEM_RESPONSE: "Assistant",
}

_CONVERSATION_PROMPT_TEMPLATE = '''You are extracting durable project memory from an excerpt of an ongoing chat conversation between a user and their writing assistant. The user's own messages are the awareness signal that authorizes remembering something - only extract a fact the user actually stated or clearly confirmed, never something merely discussed in passing.

Read the conversation excerpt below. Identify up to {max_memories} concise, durable facts worth remembering for future work on this project. Each one must be one of:
- a decision made, an objective, a methodology, a piece of terminology, or a standing guidance/preference the user actually stated (content/knowledge memory)
- a genuinely observable, recurring stylistic trait of the assistant's own replies in this excerpt (a style memory) - only include this if a real pattern is actually visible; never invent one if nothing recurs

It is completely fine to return an empty list if nothing genuinely durable was said. Do not pad the list to reach {max_memories}. Do not restate the conversation verbatim; distill each item into its own concise memory statement.

Respond with ONLY a JSON object of this exact shape:
{{"memories": [{{"record_type": "...", "content": "...", "rationale": "..."}}, ...]}}

- record_type: exactly one of objective, hypothesis, method, decision, terminology, guidance, style, other - use "style" only for an observed stylistic trait; use "guidance" for a generic standing preference that is not about writing style
- content: a concise, self-contained memory statement (one or two sentences), useful without the original conversation in front of you
- rationale: a short explanation of why this is worth remembering (optional, may be an empty string)

Project topic:
"""
{topic}
"""

Project description:
"""
{description}
"""

Conversation excerpt:
"""
{transcript}
"""
'''


def build_conversation_transcript(messages: list[Message]) -> str:
    """Same labeled, per-message-bounded transcript shape as
    `conversation_summarization.build_conversation_summary_prompt`'s own transcript section -
    duplicated rather than imported, since conversation_summarization.py is about *compacting*
    history and has no reason to know about memory extraction's separate concern."""
    return "\n".join(
        f"{_TRANSCRIPT_LABELS.get(m.direction, m.direction.value)}: {m.content.strip()[:MAX_TRANSCRIPT_MESSAGE_CHARACTERS]}"
        for m in messages
        if m.content.strip()
    )


def build_conversation_memory_extraction_prompt(*, topic: str, description: str | None, transcript: str) -> str:
    return _CONVERSATION_PROMPT_TEMPLATE.format(
        max_memories=MAX_EXTRACTED_MEMORIES,
        topic=topic,
        description=description or "(none provided)",
        transcript=transcript,
    )


def extract_memories_from_conversation(
    *, topic: str, description: str | None, transcript: str, provider: TextGenerationProvider
) -> list[ExtractedMemory]:
    prompt = build_conversation_memory_extraction_prompt(topic=topic, description=description, transcript=transcript)
    raw_response = provider.generate(prompt)
    return parse_memory_extraction_response(raw_response)
