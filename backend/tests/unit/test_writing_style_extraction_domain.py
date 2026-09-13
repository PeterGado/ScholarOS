import pytest

from app.modules.writing.domain.enums import ProfileCharacteristicType
from app.modules.writing.domain.exceptions import StyleExtractionError, UnusableWritingStyleSampleError
from app.modules.writing.domain.style_extraction import (
    MAX_CHARACTERS_PER_SAMPLE,
    MAX_SAMPLES_PER_EXTRACTION,
    ExtractedCharacteristic,
    build_style_extraction_prompt,
    decode_sample_text,
    extract_style_characteristics,
    parse_style_extraction_response,
)


class FakeProvider:
    def __init__(self, response: str):
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


VALID_RESPONSE = """{"characteristics": [
  {"characteristic_type": "structure", "signal": "Short declarative sentences.", "confidence": 0.8},
  {"characteristic_type": "vocabulary", "signal": "Frequent technical terminology.", "confidence": null}
]}"""


# --- decode_sample_text -------------------------------------------------------------------


def test_decode_sample_text_decodes_utf8():
    assert decode_sample_text(b"hello world", document_id=1) == "hello world"


def test_decode_sample_text_rejects_undecodable_bytes():
    with pytest.raises(UnusableWritingStyleSampleError):
        decode_sample_text(b"\xff\xfe\x00\x01", document_id=1)


# --- build_style_extraction_prompt (deterministic input preparation) -------------------------------------------------------------------


def test_prompt_includes_all_samples_within_bound():
    prompt = build_style_extraction_prompt(["Sample A", "Sample B"])
    assert "Sample A" in prompt
    assert "Sample B" in prompt


def test_prompt_bounds_sample_count_deterministically():
    samples = [f"Sample {i}" for i in range(MAX_SAMPLES_PER_EXTRACTION + 3)]
    prompt = build_style_extraction_prompt(samples)
    for i in range(MAX_SAMPLES_PER_EXTRACTION):
        assert f"Sample {i}" in prompt
    for i in range(MAX_SAMPLES_PER_EXTRACTION, len(samples)):
        assert f"Sample {i}" not in prompt


def test_prompt_truncates_each_sample_deterministically():
    long_sample = "x" * (MAX_CHARACTERS_PER_SAMPLE + 500)
    prompt = build_style_extraction_prompt([long_sample])
    assert "x" * MAX_CHARACTERS_PER_SAMPLE in prompt
    assert "x" * (MAX_CHARACTERS_PER_SAMPLE + 1) not in prompt


def test_prompt_preserves_caller_supplied_ordering():
    first_prompt = build_style_extraction_prompt(["Alpha", "Beta"])
    second_prompt = build_style_extraction_prompt(["Beta", "Alpha"])
    assert first_prompt.index("Alpha") < first_prompt.index("Beta")
    assert second_prompt.index("Beta") < second_prompt.index("Alpha")


def test_prompt_does_not_ask_the_model_to_write_or_imitate():
    prompt = build_style_extraction_prompt(["Sample"])
    assert "imitate" in prompt.lower()
    assert "identity" in prompt.lower()


# --- parse_style_extraction_response -------------------------------------------------------------------


def test_parses_valid_response():
    result = parse_style_extraction_response(VALID_RESPONSE)
    assert result == [
        ExtractedCharacteristic(characteristic_type=ProfileCharacteristicType.STRUCTURE, signal="Short declarative sentences.", confidence=0.8),
        ExtractedCharacteristic(characteristic_type=ProfileCharacteristicType.VOCABULARY, signal="Frequent technical terminology.", confidence=None),
    ]


def test_parses_response_wrapped_in_code_fence():
    fenced = f"```json\n{VALID_RESPONSE}\n```"
    result = parse_style_extraction_response(fenced)
    assert len(result) == 2


def test_rejects_malformed_json():
    with pytest.raises(StyleExtractionError):
        parse_style_extraction_response("not json at all")


def test_rejects_non_object_json():
    with pytest.raises(StyleExtractionError):
        parse_style_extraction_response("[1, 2, 3]")


def test_rejects_missing_characteristics_key():
    with pytest.raises(StyleExtractionError):
        parse_style_extraction_response('{"foo": "bar"}')


def test_rejects_empty_characteristics_list():
    with pytest.raises(StyleExtractionError):
        parse_style_extraction_response('{"characteristics": []}')


def test_rejects_invalid_characteristic_type():
    with pytest.raises(StyleExtractionError):
        parse_style_extraction_response('{"characteristics": [{"characteristic_type": "tone", "signal": "x"}]}')


def test_rejects_blank_signal():
    with pytest.raises(StyleExtractionError):
        parse_style_extraction_response('{"characteristics": [{"characteristic_type": "structure", "signal": ""}]}')


def test_rejects_missing_signal():
    with pytest.raises(StyleExtractionError):
        parse_style_extraction_response('{"characteristics": [{"characteristic_type": "structure"}]}')


def test_rejects_out_of_range_confidence():
    with pytest.raises(StyleExtractionError):
        parse_style_extraction_response(
            '{"characteristics": [{"characteristic_type": "structure", "signal": "x", "confidence": 1.5}]}'
        )


def test_rejects_non_numeric_confidence():
    with pytest.raises(StyleExtractionError):
        parse_style_extraction_response(
            '{"characteristics": [{"characteristic_type": "structure", "signal": "x", "confidence": "high"}]}'
        )


def test_rejects_boolean_confidence():
    """bool is a subclass of int in Python - must not silently pass as a valid confidence."""
    with pytest.raises(StyleExtractionError):
        parse_style_extraction_response(
            '{"characteristics": [{"characteristic_type": "structure", "signal": "x", "confidence": true}]}'
        )


def test_one_invalid_entry_fails_the_entire_response():
    """Mandatory: mirrors the atomicity requirement - a response with one valid and one
    invalid characteristic must raise before returning anything, so the application layer
    never sees a partial, ambiguous result to persist.
    """
    mixed = '{"characteristics": [{"characteristic_type": "structure", "signal": "Valid one."}, {"characteristic_type": "not-a-type", "signal": "Invalid."}]}'
    with pytest.raises(StyleExtractionError):
        parse_style_extraction_response(mixed)


def test_ai_output_cannot_smuggle_a_source_id_or_persistence_identifier():
    """ExtractedCharacteristic has no field for document_id/characteristic_id/profile_id -
    even if the model's JSON includes one, it is silently ignored, not persisted (Stage 4
    prompt §7/§10: the provider returns semantic data only).
    """
    response = '{"characteristics": [{"characteristic_type": "structure", "signal": "x", "source_id": 123, "characteristic_id": 999}]}'
    result = parse_style_extraction_response(response)
    assert not hasattr(result[0], "source_id")
    assert not hasattr(result[0], "characteristic_id")


# --- extract_style_characteristics (composition) -------------------------------------------------------------------


def test_extract_style_characteristics_calls_provider_with_built_prompt_and_parses_result():
    provider = FakeProvider(VALID_RESPONSE)
    result = extract_style_characteristics(["Sample text"], provider)
    assert len(result) == 2
    assert "Sample text" in provider.prompts[0]
