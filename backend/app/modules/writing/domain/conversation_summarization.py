from app.modules.writing.domain.conversation_context import CONVERSATION_SUMMARY_ORIGIN, find_latest_summary_message
from app.modules.writing.domain.entities import Message
from app.modules.writing.domain.enums import MessageDirection

CONVERSATION_SUMMARY_TRIGGER_COUNT = 20
"""Once more than this many real messages have accumulated since the last summary (or since
the conversation began, if none exists yet), the oldest ones are compacted (Persistent Brain
v2, scalable conversation memory - "conversation history should eventually be summarized/
compacted when necessary", context_assembly.py's own module docstring).
"""

CONVERSATION_SUMMARY_KEEP_RECENT = 10
"""How many of the most recent real messages stay verbatim, never folded into the summary -
must be <= CONVERSATION_SUMMARY_TRIGGER_COUNT or every trigger would summarize nothing."""

MAX_SUMMARIZED_MESSAGE_CHARACTERS = 500
"""Bounds each message's contribution to the summarization prompt itself - the summary call
must not become an unbounded-size prompt problem in its own right."""

_PROMPT_TEMPLATE = """You are compacting an ongoing conversation's older history into one concise summary, so a \
later turn can still be informed by it without re-reading every message.

Summarize the conversation excerpt below into a short paragraph capturing: what the user has \
asked for or decided, any stated preferences or constraints, and any conclusions reached. Do \
not invent anything not actually present. Write it as continuous prose, not a list.
{prior_summary_section}
Conversation excerpt to summarize:
\"\"\"
{transcript}
\"\"\"
"""

_LABELS = {
    MessageDirection.USER_REQUEST: "User",
    MessageDirection.SYSTEM_RESPONSE: "Assistant",
}


def select_messages_to_summarize(messages: list[Message]) -> list[Message]:
    """Decides *whether* and *what* to summarize (pure, no I/O). Returns the messages that
    should be folded into a new summary - everything since the last summary except the most
    recent `CONVERSATION_SUMMARY_KEEP_RECENT` - or an empty list if summarization is not yet
    warranted (fewer than `CONVERSATION_SUMMARY_TRIGGER_COUNT` real messages have accumulated
    since the last one).
    """
    ordered = sorted(messages, key=lambda m: m.sequence)
    summary = find_latest_summary_message(ordered)
    last_summary_sequence = summary.sequence if summary is not None else 0

    real_since = [
        m for m in ordered if m.sequence > last_summary_sequence and m.origin != CONVERSATION_SUMMARY_ORIGIN
    ]
    if len(real_since) <= CONVERSATION_SUMMARY_TRIGGER_COUNT:
        return []
    return real_since[:-CONVERSATION_SUMMARY_KEEP_RECENT]


def build_conversation_summary_prompt(messages: list[Message], *, prior_summary: str | None) -> str:
    transcript = "\n".join(
        f"{_LABELS.get(m.direction, m.direction.value)}: {m.content.strip()[:MAX_SUMMARIZED_MESSAGE_CHARACTERS]}"
        for m in messages
        if m.content.strip()
    )
    prior_summary_section = (
        f"\nThe conversation so far was already summarized as:\n\"\"\"\n{prior_summary.strip()}\n\"\"\"\n"
        "Fold that prior summary together with the new excerpt below into one updated summary.\n"
        if prior_summary and prior_summary.strip()
        else ""
    )
    return _PROMPT_TEMPLATE.format(prior_summary_section=prior_summary_section, transcript=transcript)
