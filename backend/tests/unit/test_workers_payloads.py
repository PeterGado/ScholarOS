import pytest

from app.workers.payloads import (
    build_process_document_idempotency_key,
    build_process_document_payload_reference,
    parse_process_document_payload_reference,
)


def test_build_and_parse_round_trip():
    reference = build_process_document_payload_reference(42)
    assert parse_process_document_payload_reference(reference) == 42


def test_payload_reference_format():
    assert build_process_document_payload_reference(7) == "process_document:7"


def test_idempotency_key_matches_payload_reference_shape():
    assert build_process_document_idempotency_key(7) == build_process_document_payload_reference(7)


def test_parsing_an_unrecognized_reference_raises_value_error():
    with pytest.raises(ValueError):
        parse_process_document_payload_reference("not_a_real_reference")


def test_parsing_a_non_numeric_suffix_raises_value_error():
    with pytest.raises(ValueError):
        parse_process_document_payload_reference("process_document:not-a-number")
