import json

import pytest

from app.ai.exceptions import ProviderRequestError
from app.ai.providers.fake import FakeAIProvider
from app.modules.knowledge.domain.semantic_classification import (
    build_batch_classification_prompt,
    build_classification_prompt,
    parse_batch_classification_response,
    parse_classification_response,
)
from app.modules.writing.domain.style_extraction import (
    build_style_extraction_prompt,
    parse_style_extraction_response,
)


def test_generate_returns_plain_text_for_an_unrecognized_prompt():
    provider = FakeAIProvider()
    result = provider.generate("Write a short introduction about coastal erosion.")
    assert isinstance(result, str)
    assert result.strip()


def test_generate_satisfies_single_classification_parsing():
    provider = FakeAIProvider()
    prompt = build_classification_prompt("Some research excerpt.")
    classification = parse_classification_response(provider.generate(prompt))
    assert classification.label


def test_generate_satisfies_batch_classification_parsing_with_matching_count():
    provider = FakeAIProvider()
    chunk_texts = ["Excerpt one.", "Excerpt two.", "Excerpt three."]
    prompt = build_batch_classification_prompt(chunk_texts)
    classifications = parse_batch_classification_response(provider.generate(prompt), expected_count=len(chunk_texts))
    assert len(classifications) == len(chunk_texts)


def test_generate_satisfies_style_extraction_parsing():
    provider = FakeAIProvider()
    prompt = build_style_extraction_prompt(["A sample of writing."])
    characteristics = parse_style_extraction_response(provider.generate(prompt))
    assert len(characteristics) >= 1
    assert characteristics[0].signal


def test_embed_and_embed_batch_return_vectors_of_matching_length():
    provider = FakeAIProvider()
    assert len(provider.embed("text")) > 0
    vectors = provider.embed_batch(["a", "b", "c"])
    assert len(vectors) == 3


def test_embed_batch_with_no_texts_returns_empty_list():
    provider = FakeAIProvider()
    assert provider.embed_batch([]) == []


def test_fail_mode_raises_on_generate_embed_and_embed_batch():
    provider = FakeAIProvider(fail=True)
    with pytest.raises(ProviderRequestError):
        provider.generate("anything")
    with pytest.raises(ProviderRequestError):
        provider.embed("anything")
    with pytest.raises(ProviderRequestError):
        provider.embed_batch(["anything"])


def test_batch_classification_output_is_a_json_array_of_the_requested_length():
    provider = FakeAIProvider()
    prompt = build_batch_classification_prompt(["a", "b"])
    payload = json.loads(provider.generate(prompt))
    assert isinstance(payload, list)
    assert len(payload) == 2
