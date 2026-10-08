from app.modules.writing.domain.conversation_context import (
    CONVERSATION_SUMMARY_ORIGIN,
    find_latest_summary_message,
    resolve_bounded_conversation_messages,
)
from app.modules.writing.domain.entities import Message
from app.modules.writing.domain.enums import MessageDirection


def _message(sequence: int, content: str, *, direction=MessageDirection.USER_REQUEST, origin=None) -> Message:
    return Message(
        conversation_id=1, sequence=sequence, direction=direction, content=content, message_id=sequence, origin=origin
    )


def test_no_summary_yet_is_identical_to_plain_bounding():
    # Three complete user/reply pairs - a realistic conversation shape (resolve_bounded_
    # conversation_messages is only ever called with messages strictly before the one about to
    # be answered, so a real prior-messages list always ends on a SYSTEM_RESPONSE, not a
    # trailing unanswered USER_REQUEST - see the "unanswered messages" tests below for that case).
    messages = [
        _message(1, "Message 1."),
        _message(2, "Message 2.", direction=MessageDirection.SYSTEM_RESPONSE),
        _message(3, "Message 3."),
        _message(4, "Message 4.", direction=MessageDirection.SYSTEM_RESPONSE),
        _message(5, "Message 5."),
        _message(6, "Message 6.", direction=MessageDirection.SYSTEM_RESPONSE),
    ]

    resolved = resolve_bounded_conversation_messages(messages, max_recent=3)

    assert len(resolved) == 3
    assert [r.content for r in resolved] == ["Message 4.", "Message 5.", "Message 6."]
    assert all(not r.is_summary for r in resolved)


def test_finds_the_latest_of_several_summary_messages():
    messages = [
        _message(1, "First summary.", origin=CONVERSATION_SUMMARY_ORIGIN),
        _message(2, "Real message."),
        _message(5, "Second summary.", origin=CONVERSATION_SUMMARY_ORIGIN),
    ]

    latest = find_latest_summary_message(messages)

    assert latest is not None
    assert latest.content == "Second summary."


def test_no_summary_message_returns_none():
    messages = [_message(1, "Just a real message.")]

    assert find_latest_summary_message(messages) is None


def test_resolved_context_includes_the_summary_and_only_messages_after_it():
    messages = [
        _message(1, "Old message 1."),
        _message(2, "Old message 2.", direction=MessageDirection.SYSTEM_RESPONSE),
        _message(3, "Rolling summary of messages 1-2.", origin=CONVERSATION_SUMMARY_ORIGIN),
        _message(4, "New message."),
        _message(5, "Reply to the new message.", direction=MessageDirection.SYSTEM_RESPONSE),
    ]

    resolved = resolve_bounded_conversation_messages(messages, max_recent=10)

    assert len(resolved) == 3
    assert resolved[0].is_summary is True
    assert resolved[0].content == "Rolling summary of messages 1-2."
    assert resolved[1].is_summary is False
    assert resolved[1].content == "New message."
    assert resolved[2].content == "Reply to the new message."
    # The raw messages the summary already covers are never re-included.
    assert "Old message 1." not in [r.content for r in resolved]


def test_messages_after_the_summary_are_still_bounded_to_max_recent():
    pairs = []
    for sequence in range(2, 20):
        direction = MessageDirection.USER_REQUEST if sequence % 2 == 0 else MessageDirection.SYSTEM_RESPONSE
        pairs.append(_message(sequence, f"Message {sequence}.", direction=direction))
    messages = [_message(1, "Summary.", origin=CONVERSATION_SUMMARY_ORIGIN), *pairs]

    resolved = resolve_bounded_conversation_messages(messages, max_recent=3)

    assert resolved[0].is_summary is True
    assert [r.content for r in resolved[1:]] == ["Message 17.", "Message 18.", "Message 19."]


# --- Unanswered messages never poison a later prompt (2026-09-30) -------------------------


def test_a_message_with_no_reply_yet_is_excluded_from_context():
    """A live test found why this matters: a message the AI provider's safety filter blocked
    stayed in conversation history with no reply, so its own text kept getting resent as
    context on every later message - which caused the safety filter to reject every subsequent
    message in that same conversation too, even unrelated, benign ones. Excluding any message
    with no immediately-following reply fixes this generally, not just for safety blocks - a
    permanently rate-limited or otherwise failed message has the identical poisoning risk.
    """
    messages = [_message(1, "A message whose reply never arrived.")]

    resolved = resolve_bounded_conversation_messages(messages, max_recent=10)

    assert resolved == ()


def test_only_the_unanswered_message_is_excluded_not_earlier_answered_ones():
    messages = [
        _message(1, "Earlier question."),
        _message(2, "Earlier answer.", direction=MessageDirection.SYSTEM_RESPONSE),
        _message(3, "A message whose reply never arrived."),
    ]

    resolved = resolve_bounded_conversation_messages(messages, max_recent=10)

    assert [r.content for r in resolved] == ["Earlier question.", "Earlier answer."]


def test_an_unanswered_message_is_excluded_even_when_not_the_last_one():
    messages = [
        _message(1, "First message, never answered."),
        _message(2, "Second question."),
        _message(3, "Second answer.", direction=MessageDirection.SYSTEM_RESPONSE),
    ]

    resolved = resolve_bounded_conversation_messages(messages, max_recent=10)

    assert [r.content for r in resolved] == ["Second question.", "Second answer."]


def test_a_real_system_response_is_never_itself_excluded():
    messages = [
        _message(1, "Question."),
        _message(2, "Answer.", direction=MessageDirection.SYSTEM_RESPONSE),
    ]

    resolved = resolve_bounded_conversation_messages(messages, max_recent=10)

    assert [r.content for r in resolved] == ["Question.", "Answer."]
