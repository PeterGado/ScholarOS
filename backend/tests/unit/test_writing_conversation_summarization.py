from app.modules.writing.domain.conversation_context import CONVERSATION_SUMMARY_ORIGIN
from app.modules.writing.domain.conversation_summarization import (
    CONVERSATION_SUMMARY_KEEP_RECENT,
    CONVERSATION_SUMMARY_TRIGGER_COUNT,
    build_conversation_summary_prompt,
    select_messages_to_summarize,
)
from app.modules.writing.domain.entities import Message
from app.modules.writing.domain.enums import MessageDirection


def _message(sequence: int, content: str, *, direction=MessageDirection.USER_REQUEST, origin=None) -> Message:
    return Message(
        conversation_id=1, sequence=sequence, direction=direction, content=content, message_id=sequence, origin=origin
    )


def test_below_the_trigger_count_selects_nothing():
    messages = [_message(i, f"Message {i}.") for i in range(1, CONVERSATION_SUMMARY_TRIGGER_COUNT)]

    assert select_messages_to_summarize(messages) == []


def test_above_the_trigger_count_summarizes_everything_except_the_most_recent():
    total = CONVERSATION_SUMMARY_TRIGGER_COUNT + 1
    messages = [_message(i, f"Message {i}.") for i in range(1, total + 1)]

    to_summarize = select_messages_to_summarize(messages)

    assert len(to_summarize) == total - CONVERSATION_SUMMARY_KEEP_RECENT
    # The most recent CONVERSATION_SUMMARY_KEEP_RECENT messages are never included.
    kept_recent_content = {f"Message {i}." for i in range(total - CONVERSATION_SUMMARY_KEEP_RECENT + 1, total + 1)}
    assert kept_recent_content.isdisjoint({m.content for m in to_summarize})


def test_only_counts_real_messages_since_the_last_summary():
    old = [_message(i, f"Old {i}.") for i in range(1, 30)]
    summary = _message(30, "Summary of the old messages.", origin=CONVERSATION_SUMMARY_ORIGIN)
    few_new = [_message(i, f"New {i}.") for i in range(31, 35)]

    to_summarize = select_messages_to_summarize(old + [summary] + few_new)

    # Only 4 real messages exist since the summary - well under the trigger count.
    assert to_summarize == []


def test_prompt_includes_the_transcript():
    messages = [
        _message(1, "What is the methodology?"),
        _message(2, "A LIDAR survey.", direction=MessageDirection.SYSTEM_RESPONSE),
    ]

    prompt = build_conversation_summary_prompt(messages, prior_summary=None)

    assert "What is the methodology?" in prompt
    assert "A LIDAR survey." in prompt
    assert "User:" in prompt
    assert "Assistant:" in prompt


def test_prompt_folds_in_a_prior_summary_when_present():
    messages = [_message(1, "New message.")]

    prompt = build_conversation_summary_prompt(messages, prior_summary="Earlier, the user set the topic.")

    assert "Earlier, the user set the topic." in prompt
    assert "New message." in prompt


def test_prompt_bounds_each_messages_contribution():
    long_message = [_message(1, "x" * 5000)]

    prompt = build_conversation_summary_prompt(long_message, prior_summary=None)

    assert len(prompt) < 5500
