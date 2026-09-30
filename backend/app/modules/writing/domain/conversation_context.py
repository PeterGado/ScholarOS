from app.modules.writing.domain.context_assembly import ContextConversationMessage
from app.modules.writing.domain.entities import Message
from app.modules.writing.domain.enums import MessageDirection

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
    real_messages = _exclude_unanswered_user_messages(real_messages)
    recent = real_messages[-max_recent:] if max_recent > 0 else []

    resolved = [
        ContextConversationMessage(direction=m.direction, content=m.content, is_summary=False) for m in recent
    ]
    if summary is not None:
        resolved.insert(
            0, ContextConversationMessage(direction=summary.direction, content=summary.content, is_summary=True)
        )
    return tuple(resolved)


def _exclude_unanswered_user_messages(messages: list[Message]) -> list[Message]:
    """A user message whose reply never arrived - still mid-flight, or permanently failed (a
    safety block, an exhausted rate limit, any other terminal failure) - has no matching
    SYSTEM_RESPONSE message immediately after it. Left in place, it gets replayed into every
    future prompt for this conversation.

    2026-09-30: a real live test found exactly why that's harmful, not just untidy. A message
    containing harassing/abusive language was correctly blocked by the AI provider's safety
    filtering - but because the blocked message stayed in conversation history with no reply,
    its own text kept getting resent as part of RELEVANT CONVERSATION CONTEXT on every later
    message, which caused the safety filter to reject every subsequent message in that same
    conversation too, even entirely unrelated, benign ones. One blocked message poisoned the
    whole thread going forward, with no way to recover short of starting a new conversation.

    Filtering out any user message without an immediately-following reply fixes this generally
    (not just for safety blocks - a rate-limited-to-exhaustion or otherwise permanently failed
    message has the identical poisoning risk) and costs nothing for the ordinary case: a
    successful reply is always persisted directly after its user message, so this never drops
    anything from a normal conversation.
    """
    kept: list[Message] = []
    for index, message in enumerate(messages):
        if message.direction != MessageDirection.USER_REQUEST:
            kept.append(message)
            continue
        has_reply = index + 1 < len(messages) and messages[index + 1].direction == MessageDirection.SYSTEM_RESPONSE
        if has_reply:
            kept.append(message)
    return kept
