import pytest

from app.workers.payloads import (
    build_generate_draft_version_payload_reference,
    build_process_document_idempotency_key,
    build_process_document_payload_reference,
    parse_generate_draft_version_payload_reference,
    parse_process_document_payload_reference,
)
from app.modules.writing.domain.context_assembly import ContextAssemblyInput, ContextEvidence


def test_build_and_parse_round_trip():
    reference = build_process_document_payload_reference(42)
    assert parse_process_document_payload_reference(reference) == 42


def test_payload_reference_format():
    assert build_process_document_payload_reference(7) == "process_document:7"


def test_idempotency_key_matches_payload_reference_shape():
    assert build_process_document_idempotency_key(
        7) == build_process_document_payload_reference(7)


def test_parsing_an_unrecognized_reference_raises_value_error():
    with pytest.raises(ValueError):
        parse_process_document_payload_reference("not_a_real_reference")


def test_parsing_a_non_numeric_suffix_raises_value_error():
    with pytest.raises(ValueError):
        parse_process_document_payload_reference(
            "process_document:not-a-number")


def test_generation_payload_round_trips_context_and_request_identity():
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="Write a paragraph.",
        evidence=(ContextEvidence(
            chunk_id=4, content="Evidence.", summary=None, score=0.9),),
    )

    payload, idempotency_key = build_generate_draft_version_payload_reference(
        12, context, request_id="request-1"
    )

    draft_id, parsed_context, request_id = parse_generate_draft_version_payload_reference(
        payload)
    assert draft_id == 12
    assert parsed_context == context
    assert request_id == "request-1"
    assert idempotency_key == "generate_draft_version:request-1"


def test_generation_payload_rejects_malformed_reference():
    with pytest.raises(ValueError):
        parse_generate_draft_version_payload_reference(
            "generate_draft_version:{bad-json")


def test_generation_payload_rejects_context_over_existing_column_limit():
    context = ContextAssemblyInput(topic="Topic", instructions="x" * 1000)

    with pytest.raises(ValueError, match="payload limit"):
        build_generate_draft_version_payload_reference(
            1, context, request_id="request-1")
