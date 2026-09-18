import pytest

from app.modules.writing.domain.entities import Message
from app.modules.writing.domain.enums import MemoryRecordType, MessageDirection
from app.modules.writing.domain.exceptions import MemoryExtractionError
from app.modules.writing.domain.memory_extraction import (
    ExtractedMemory,
    build_conversation_memory_extraction_prompt,
    build_conversation_transcript,
    extract_memories_from_conversation,
    parse_memory_extraction_response,
)


class FakeTextProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def _message(direction: MessageDirection, content: str, sequence: int = 1) -> Message:
    return Message(conversation_id=1, sequence=sequence, direction=direction, content=content)


# --- build_conversation_transcript -----------------------------------------------------------


def test_transcript_labels_user_and_assistant_messages():
    messages = [
        _message(MessageDirection.USER_REQUEST, "Always cite in APA.", sequence=1),
        _message(MessageDirection.SYSTEM_RESPONSE, "Understood, I will use APA.", sequence=2),
    ]

    transcript = build_conversation_transcript(messages)

    assert "User: Always cite in APA." in transcript
    assert "Assistant: Understood, I will use APA." in transcript


def test_transcript_bounds_each_messages_contribution():
    long_content = "x" * 5000
    messages = [_message(MessageDirection.USER_REQUEST, long_content, sequence=1)]

    transcript = build_conversation_transcript(messages)

    assert len(transcript) < len(long_content)


# --- build_conversation_memory_extraction_prompt ----------------------------------------------


def test_prompt_includes_topic_description_and_transcript():
    prompt = build_conversation_memory_extraction_prompt(
        topic="Erosion on barrier islands",
        description="A field report for an environmental science course.",
        transcript="User: Always cite in APA.",
    )

    assert "Erosion on barrier islands" in prompt
    assert "A field report for an environmental science course." in prompt
    assert "User: Always cite in APA." in prompt


def test_prompt_handles_a_missing_description_gracefully():
    prompt = build_conversation_memory_extraction_prompt(topic="Topic", description=None, transcript="User: Hi.")

    assert "(none provided)" in prompt


# --- parse_memory_extraction_response -------------------------------------------------------


def test_parses_a_well_formed_single_memory_response():
    raw = '{"memories": [{"record_type": "decision", "content": "Use LIDAR survey data.", "rationale": "Approved by reviewer."}]}'

    extracted = parse_memory_extraction_response(raw)

    assert extracted == [
        ExtractedMemory(
            record_type=MemoryRecordType.DECISION, content="Use LIDAR survey data.", rationale="Approved by reviewer."
        )
    ]


def test_parses_multiple_memories_including_a_style_observation():
    """Persistent Brain v3 audit fix: STYLE is a dedicated record_type, distinct from GUIDANCE
    (a generic standing preference) - the two must never be conflated again.
    """
    raw = (
        '{"memories": ['
        '{"record_type": "decision", "content": "Use LIDAR survey data.", "rationale": ""},'
        '{"record_type": "style", "content": "Consistently uses short declarative sentences.", "rationale": "Style observation."}'
        "]}"
    )

    extracted = parse_memory_extraction_response(raw)

    assert len(extracted) == 2
    assert extracted[0].record_type == MemoryRecordType.DECISION
    assert extracted[1].record_type == MemoryRecordType.STYLE
    assert "short declarative sentences" in extracted[1].content


def test_guidance_and_style_are_distinct_record_types():
    raw = (
        '{"memories": ['
        '{"record_type": "guidance", "content": "Always cite the funding source.", "rationale": ""},'
        '{"record_type": "style", "content": "Prefers passive voice in methodology sections.", "rationale": ""}'
        "]}"
    )

    extracted = parse_memory_extraction_response(raw)

    assert extracted[0].record_type == MemoryRecordType.GUIDANCE
    assert extracted[1].record_type == MemoryRecordType.STYLE
    assert extracted[0].record_type != extracted[1].record_type


def test_parses_an_empty_memories_list_as_valid():
    raw = '{"memories": []}'

    extracted = parse_memory_extraction_response(raw)

    assert extracted == []


def test_parses_a_response_wrapped_in_a_code_fence():
    raw = '```json\n{"memories": [{"record_type": "method", "content": "Uses LIDAR.", "rationale": ""}]}\n```'

    extracted = parse_memory_extraction_response(raw)

    assert extracted[0].record_type == MemoryRecordType.METHOD
    assert extracted[0].rationale is None  # blank rationale normalizes to None


def test_rejects_invalid_json():
    with pytest.raises(MemoryExtractionError, match="not valid JSON"):
        parse_memory_extraction_response("not json at all")


def test_rejects_a_non_object_json_payload():
    with pytest.raises(MemoryExtractionError, match="not a JSON object"):
        parse_memory_extraction_response("[1, 2, 3]")


def test_rejects_a_response_missing_the_memories_list():
    with pytest.raises(MemoryExtractionError, match="'memories' list"):
        parse_memory_extraction_response('{"record_type": "decision", "content": "x", "rationale": ""}')


def test_rejects_more_than_the_maximum_number_of_memories():
    memories = [{"record_type": "other", "content": f"Item {i}.", "rationale": ""} for i in range(10)]
    import json

    with pytest.raises(MemoryExtractionError, match="more than"):
        parse_memory_extraction_response(json.dumps({"memories": memories}))


def test_rejects_an_unrecognized_record_type_rather_than_guessing_one():
    raw = '{"memories": [{"record_type": "not-a-real-type", "content": "Something.", "rationale": ""}]}'

    with pytest.raises(MemoryExtractionError, match="not one of the approved values"):
        parse_memory_extraction_response(raw)


def test_rejects_missing_content():
    raw = '{"memories": [{"record_type": "guidance", "content": "", "rationale": ""}]}'

    with pytest.raises(MemoryExtractionError, match="content was missing or empty"):
        parse_memory_extraction_response(raw)


# --- extract_memories_from_conversation (prompt + provider + parse, end to end) --------------


def test_extract_memories_from_conversation_calls_the_provider_with_the_built_prompt_and_parses_its_response():
    provider = FakeTextProvider(
        '{"memories": [{"record_type": "objective", "content": "Focus on the north end.", "rationale": ""}]}'
    )

    extracted = extract_memories_from_conversation(
        topic="Topic", description="Description.", transcript="User: Focus on the north end going forward.", provider=provider
    )

    assert len(extracted) == 1
    assert extracted[0].record_type == MemoryRecordType.OBJECTIVE
    assert extracted[0].content == "Focus on the north end."
    assert len(provider.prompts) == 1
    assert "Topic" in provider.prompts[0]


def test_extract_memories_from_conversation_returns_empty_list_for_an_empty_memories_response():
    provider = FakeTextProvider('{"memories": []}')

    extracted = extract_memories_from_conversation(
        topic="Topic", description=None, transcript="User: hello.", provider=provider
    )

    assert extracted == []
