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
    messages = [_message(i, f"Message {i}.") for i in range(1, 6)]

    resolved = resolve_bounded_conversation_messages(messages, max_recent=3)

    assert len(resolved) == 3
    assert [r.content for r in resolved] == ["Message 3.", "Message 4.", "Message 5."]
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
        _message(2, "Old message 2."),
        _message(3, "Rolling summary of messages 1-2.", origin=CONVERSATION_SUMMARY_ORIGIN),
        _message(4, "New message."),
    ]

    resolved = resolve_bounded_conversation_messages(messages, max_recent=10)

    assert len(resolved) == 2
    assert resolved[0].is_summary is True
    assert resolved[0].content == "Rolling summary of messages 1-2."
    assert resolved[1].is_summary is False
    assert resolved[1].content == "New message."
    # The raw messages the summary already covers are never re-included.
    assert "Old message 1." not in [r.content for r in resolved]


def test_messages_after_the_summary_are_still_bounded_to_max_recent():
    messages = [_message(1, "Summary.", origin=CONVERSATION_SUMMARY_ORIGIN)] + [
        _message(i, f"Message {i}.") for i in range(2, 20)
    ]

    resolved = resolve_bounded_conversation_messages(messages, max_recent=3)

    assert resolved[0].is_summary is True
    assert [r.content for r in resolved[1:]] == ["Message 17.", "Message 18.", "Message 19."]
