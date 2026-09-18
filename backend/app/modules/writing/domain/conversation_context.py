from app.modules.writing.domain.context_assembly import ContextConversationMessage
from app.modules.writing.domain.entities import Message

CONVERSATION_SUMMARY_ORIGIN = "conversation_summary"
"""The `Message.origin` marker distinguishing a rolling AI-generated summary from a real
exchange (Persistent Brain v2, scalable conversation memory). Deliberately reuses the existing
Message entity and its free-form `origin` field rather than adding a new column or a new
entity - the same "reuse a frozen, genuinely free-form field" discipline already used for
`Conversation.title`'s draft-association convention.
"""


def find_latest_summary_message(messages: list[Message]) -> Message | None:
    """The most recent rolling summary Message in a Conversation's history, if any - shared by
    `resolve_bounded_conversation_messages` (rendering) and `conversation_summarization.
    select_messages_to_summarize` (deciding whether/what to re-summarize next).
    """
    latest: Message | None = None
    for message in sorted(messages, key=lambda m: m.sequence):
        if message.origin == CONVERSATION_SUMMARY_ORIGIN:
            latest = message
    return latest


def resolve_bounded_conversation_messages(
    messages: list[Message], *, max_recent: int
) -> tuple[ContextConversationMessage, ...]:
    """Resolves a Conversation's full persisted message history into the bounded, summary-aware
    sequence `ContextAssemblyInput.conversation_messages` expects.

    Finds the most recent rolling summary Message (if any - see `CONVERSATION_SUMMARY_ORIGIN`)
    and returns it, marked `is_summary=True`, followed by every real message after it, bounded
    to the most recent `max_recent`. With no summary yet (the common case for a short
    conversation), this is exactly "the last `max_recent` real messages" - identical to the
    plain bounding Persistent Brain v1 shipped, so applying this uniformly changes nothing for
    a conversation that has never been compacted.

    Pure and read-only: this function never decides *when* to summarize or persist anything -
    see `conversation_summarization.py` and `SummarizeConversationIfNeededUseCase` for that.
    """
    ordered = sorted(messages, key=lambda m: m.sequence)
    summary = find_latest_summary_message(ordered)

    real_messages = (
        [m for m in ordered if m.sequence > summary.sequence and m.origin != CONVERSATION_SUMMARY_ORIGIN]
        if summary is not None
        else [m for m in ordered if m.origin != CONVERSATION_SUMMARY_ORIGIN]
    )
    recent = real_messages[-max_recent:] if max_recent > 0 else []

    resolved = [
        ContextConversationMessage(direction=m.direction, content=m.content, is_summary=False) for m in recent
    ]
    if summary is not None:
        resolved.insert(
            0, ContextConversationMessage(direction=summary.direction, content=summary.content, is_summary=True)
        )
    return tuple(resolved)
