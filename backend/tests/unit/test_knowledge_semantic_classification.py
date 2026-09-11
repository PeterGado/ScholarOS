import pytest

from app.modules.knowledge.domain.enums import KnowledgeElementType
from app.modules.knowledge.domain.exceptions import SemanticExtractionError
from app.modules.knowledge.domain.semantic_classification import (
    ChunkClassification,
    classify_chunk,
    parse_classification_response,
)


class FakeTextGenerationProvider:
    def __init__(self, response: str):
        self.response = response
        self.prompts_seen: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts_seen.append(prompt)
        return self.response


# --- parse_classification_response -----------------------------------------------------


def test_parses_a_valid_json_response():
    result = parse_classification_response(
        '{"element_type": "concept", "label": "Sample rate", "description": "Describes the data collection cadence."}'
    )
    assert result == ChunkClassification(
        element_type=KnowledgeElementType.CONCEPT,
        label="Sample rate",
        description="Describes the data collection cadence.",
    )


def test_parses_a_response_wrapped_in_a_markdown_json_code_fence():
    response = '```json\n{"element_type": "claim", "label": "Main finding", "description": "X causes Y."}\n```'
    result = parse_classification_response(response)
    assert result.element_type == KnowledgeElementType.CLAIM
    assert result.label == "Main finding"


def test_parses_a_response_wrapped_in_a_bare_code_fence():
    response = '```\n{"element_type": "method", "label": "Survey design", "description": null}\n```'
    result = parse_classification_response(response)
    assert result.element_type == KnowledgeElementType.METHOD
    assert result.description is None


def test_missing_description_is_none():
    result = parse_classification_response('{"element_type": "theme", "label": "Recurring topic"}')
    assert result.description is None


def test_malformed_json_raises_semantic_extraction_error():
    with pytest.raises(SemanticExtractionError):
        parse_classification_response("this is not json at all")


def test_non_object_json_raises_semantic_extraction_error():
    with pytest.raises(SemanticExtractionError):
        parse_classification_response("[1, 2, 3]")


def test_invalid_element_type_is_rejected_not_coerced():
    with pytest.raises(SemanticExtractionError):
        parse_classification_response('{"element_type": "not-a-real-type", "label": "X"}')


def test_missing_element_type_raises_semantic_extraction_error():
    with pytest.raises(SemanticExtractionError):
        parse_classification_response('{"label": "X", "description": "Y"}')


def test_missing_label_raises_semantic_extraction_error():
    with pytest.raises(SemanticExtractionError):
        parse_classification_response('{"element_type": "concept"}')


def test_empty_label_raises_semantic_extraction_error():
    with pytest.raises(SemanticExtractionError):
        parse_classification_response('{"element_type": "concept", "label": "   "}')


# --- classify_chunk ------------------------------------------------------------------------


def test_classify_chunk_sends_the_chunk_text_in_the_prompt_and_parses_the_response():
    provider = FakeTextGenerationProvider('{"element_type": "concept", "label": "Test", "description": "d"}')
    result = classify_chunk("Some excerpt text.", provider)

    assert result.element_type == KnowledgeElementType.CONCEPT
    assert len(provider.prompts_seen) == 1
    assert "Some excerpt text." in provider.prompts_seen[0]


def test_classify_chunk_propagates_semantic_extraction_error_from_a_bad_response():
    provider = FakeTextGenerationProvider("not valid json")
    with pytest.raises(SemanticExtractionError):
        classify_chunk("Some excerpt text.", provider)
