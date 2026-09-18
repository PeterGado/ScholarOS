"""Shared payload_reference formats for pipeline stages.

`Work Item.kind` is fixed to `pipeline_stage`/`domain_event` (04_Logical_Data_Model.md §3.20)
- the specific unit of work is encoded in `payload_reference` instead (Backend_Slice2_
Implementation_Plan.md §5's correction). One shared module so the enqueue site
(UploadResearchDocumentUseCase) and the consume site (the executor) never drift apart on the
format.

`payload_reference` is documented as "Short Text - reference to the work payload"
(04_Logical_Data_Model.md §3.20), the same logical type as `ResearchDocument.
content_reference` (§3.4) - a pointer, not the payload itself. `build_process_document_
payload_reference` already follows that: `process_document:<id>` is a genuine reference.
`build_generate_chat_reply_payload_reference` follows the same pattern - see its own
docstring for why the context is snapshotted to the content store rather than inlined.
"""

import json
from uuid import uuid4

from app.modules.document.domain.ports import ContentStore
from app.modules.writing.domain.context_assembly import (
    ContextAssemblyInput,
    ContextConversationMessage,
    ContextEvidence,
    ContextEvidenceSource,
    ContextMemory,
    ContextStyleSignal,
)
from app.modules.writing.domain.enums import MemoryRecordType, MessageDirection, ProfileCharacteristicType

_PROCESS_DOCUMENT_PREFIX = "process_document:"
_GENERATE_CHAT_REPLY_PREFIX = "generate_chat_reply:"
# No longer sized against a serialized context (see module docstring) - this now only bounds
# the reference itself (conversation_id + message_id + request_id + content-store key), which
# is always small and of roughly fixed size regardless of context size. Kept as a defensive
# assertion, not a routine limitation.
_MAX_PAYLOAD_REFERENCE_LENGTH = 512


def build_process_document_payload_reference(document_id: int) -> str:
    return f"{_PROCESS_DOCUMENT_PREFIX}{document_id}"


def build_process_document_idempotency_key(document_id: int) -> str:
    """Same shape as the payload reference - guarantees at most one Work Item is ever
    enqueued per document (the idempotency_key column is unique), which also means "does a
    Work Item already exist for this document" needs no separate query.
    """
    return build_process_document_payload_reference(document_id)


def parse_process_document_payload_reference(payload_reference: str) -> int:
    if not payload_reference.startswith(_PROCESS_DOCUMENT_PREFIX):
        raise ValueError(
            f"Unrecognized payload reference: {payload_reference!r}")
    return int(payload_reference[len(_PROCESS_DOCUMENT_PREFIX):])


def build_generate_chat_reply_payload_reference(
    conversation_id: int,
    user_message_id: int,
    context: ContextAssemblyInput,
    content_store: ContentStore,
    *,
    request_id: str | None = None,
) -> tuple[str, str]:
    """Persistent Brain Decision 3: an Agent Workspace chat message, resolved into a real
    `ContextAssemblyInput` and enqueued - the (potentially large - evidence chunk content,
    style signals, memory) context is written to the existing content-addressed `ContentStore`
    (the same abstraction and object-store category `UploadResearchDocumentUseCase` already
    writes into, ADR-004 §5) and only a short reference to it is embedded in
    `payload_reference`, exactly mirroring `ResearchDocument.content_reference` - never inlined
    directly (Context Assembly's own default budget is 12,000 characters across up to 10
    evidence chunks, far past what a single Work Item column should hold).
    """
    request_id = request_id or uuid4().hex
    context_json = json.dumps(_context_to_dict(context), separators=(",", ":"), sort_keys=True)
    context_reference = content_store.save(context_json.encode("utf-8"), extension="json")

    payload_reference = (
        f"{_GENERATE_CHAT_REPLY_PREFIX}{conversation_id}:{user_message_id}:{request_id}:{context_reference}"
    )
    if len(payload_reference) > _MAX_PAYLOAD_REFERENCE_LENGTH:
        raise ValueError("generate_chat_reply payload reference unexpectedly exceeds the Work Item column limit")
    return payload_reference, f"{_GENERATE_CHAT_REPLY_PREFIX}{request_id}"


def parse_generate_chat_reply_conversation_id(payload_reference: str) -> int:
    """Cheaply extracts just the conversation_id a `generate_chat_reply` Work Item belongs to,
    without reading its content-store-backed context (unlike `parse_generate_chat_reply_
    payload_reference`) - all a status/ownership check needs, per `GetChatReplyStatusUseCase`'s
    own docstring for why it must confirm a work_item_id actually belongs to the conversation
    the caller claims, not just that the conversation itself is theirs.
    """
    if not payload_reference.startswith(_GENERATE_CHAT_REPLY_PREFIX):
        raise ValueError(f"Unrecognized payload reference: {payload_reference!r}")
    try:
        remainder = payload_reference[len(_GENERATE_CHAT_REPLY_PREFIX):]
        conversation_id_text = remainder.split(":", 1)[0]
        conversation_id = int(conversation_id_text)
        if conversation_id < 1:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"Malformed chat reply payload reference: {payload_reference!r}") from exc
    return conversation_id


def parse_generate_chat_reply_payload_reference(
    payload_reference: str, content_store: ContentStore
) -> tuple[int, int, ContextAssemblyInput, str]:
    if not payload_reference.startswith(_GENERATE_CHAT_REPLY_PREFIX):
        raise ValueError(f"Unrecognized payload reference: {payload_reference!r}")
    try:
        remainder = payload_reference[len(_GENERATE_CHAT_REPLY_PREFIX):]
        conversation_id_text, message_id_text, request_id, context_reference = remainder.split(":", 3)
        conversation_id = int(conversation_id_text)
        user_message_id = int(message_id_text)
        if conversation_id < 1 or user_message_id < 1 or not request_id or not context_reference:
            raise ValueError
        context_json = content_store.read(context_reference)
        context = _context_from_dict(json.loads(context_json))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Malformed chat reply payload reference: {payload_reference!r}") from exc
    return conversation_id, user_message_id, context, request_id


def _context_to_dict(context: ContextAssemblyInput) -> dict:
    return {
        "topic": context.topic,
        "description": context.description,
        "instructions": context.instructions,
        "max_characters": context.max_characters,
        "max_evidence": context.max_evidence,
        "max_conversation_messages": context.max_conversation_messages,
        "max_memories": context.max_memories,
        "conversation_messages": [
            {"direction": item.direction.value, "content": item.content, "is_summary": item.is_summary}
            for item in context.conversation_messages
        ],
        "evidence": [
            {
                "chunk_id": item.chunk_id,
                "content": item.content,
                "summary": item.summary,
                "score": item.score,
                "sources": [
                    {"document_id": source.document_id,
                        "document_title": source.document_title}
                    for source in item.sources
                ],
            }
            for item in context.evidence
        ],
        "style_signals": [
            {
                "characteristic_type": item.characteristic_type.value,
                "signal": item.signal,
                "confidence": item.confidence,
            }
            for item in context.style_signals
        ],
        "memories": [
            {"record_type": item.record_type.value,
                "content": item.content, "rationale": item.rationale}
            for item in context.memories
        ],
    }


def _context_from_dict(payload: dict) -> ContextAssemblyInput:
    if not isinstance(payload, dict):
        raise ValueError
    return ContextAssemblyInput(
        topic=payload["topic"],
        description=payload.get("description"),
        instructions=payload["instructions"],
        max_characters=payload["max_characters"],
        max_evidence=payload["max_evidence"],
        max_conversation_messages=payload.get("max_conversation_messages", 10),
        max_memories=payload.get("max_memories", 20),
        conversation_messages=tuple(
            ContextConversationMessage(
                direction=MessageDirection(item["direction"]),
                content=item["content"],
                is_summary=item.get("is_summary", False),
            )
            for item in payload.get("conversation_messages", [])
        ),
        evidence=tuple(
            ContextEvidence(
                chunk_id=item["chunk_id"],
                content=item["content"],
                summary=item["summary"],
                score=item["score"],
                sources=tuple(
                    ContextEvidenceSource(
                        document_id=source["document_id"], document_title=source["document_title"]
                    )
                    for source in item.get("sources", [])
                ),
            )
            for item in payload.get("evidence", [])
        ),
        style_signals=tuple(
            ContextStyleSignal(
                characteristic_type=ProfileCharacteristicType(
                    item["characteristic_type"]),
                signal=item["signal"],
                confidence=item["confidence"],
            )
            for item in payload.get("style_signals", [])
        ),
        memories=tuple(
            ContextMemory(
                record_type=MemoryRecordType(item["record_type"]),
                content=item["content"],
                rationale=item["rationale"],
            )
            for item in payload.get("memories", [])
        ),
    )
