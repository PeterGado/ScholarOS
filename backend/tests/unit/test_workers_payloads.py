import pytest

from app.modules.writing.domain.context_assembly import ContextAssemblyInput, ContextEvidence
from app.workers.payloads import (
    build_generate_chat_reply_payload_reference,
    build_process_document_idempotency_key,
    build_process_document_payload_reference,
    parse_generate_chat_reply_payload_reference,
    parse_process_document_payload_reference,
)


class FakeContentStore:
    """In-memory ContentStore fake - save()/read() round-trip, no filesystem, no network."""

    def __init__(self) -> None:
        self._by_reference: dict[str, bytes] = {}

    def save(self, content: bytes, *, extension: str = "") -> str:
        reference = f"ref-{len(self._by_reference)}{('.' + extension) if extension else ''}"
        self._by_reference[reference] = content
        return reference

    def read(self, reference: str) -> bytes:
        return self._by_reference[reference]

    def exists(self, reference: str) -> bool:
        return reference in self._by_reference


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


def test_chat_reply_payload_round_trips_context_and_request_identity():
    content_store = FakeContentStore()
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="Write a paragraph.",
        evidence=(ContextEvidence(chunk_id=4, content="Evidence.", summary=None, score=0.9),),
    )

    payload, idempotency_key = build_generate_chat_reply_payload_reference(
        12, 5, context, content_store, request_id="request-1"
    )

    conversation_id, user_message_id, parsed_context, request_id = parse_generate_chat_reply_payload_reference(
        payload, content_store
    )
    assert conversation_id == 12
    assert user_message_id == 5
    assert parsed_context == context
    assert request_id == "request-1"
    assert idempotency_key == "generate_chat_reply:request-1"


def test_chat_reply_payload_reference_is_short_regardless_of_context_size():
    """The defect this replaces: an earlier version inlined the full serialized context into
    payload_reference and rejected anything over 512 characters - unusable for any context
    with real, evidence-sized content. The context is now written to the content store, so
    payload_reference stays a short pointer no matter how large the context is.
    """
    content_store = FakeContentStore()
    realistic_context = ContextAssemblyInput(
        topic="A" * 200,
        instructions="B" * 500,
        evidence=tuple(
            ContextEvidence(chunk_id=index, content="Evidence paragraph. " * 100, summary=None, score=0.9)
            for index in range(10)
        ),
    )

    payload, _idempotency_key = build_generate_chat_reply_payload_reference(
        1, 1, realistic_context, content_store, request_id="request-1"
    )

    assert len(payload) < 200
    conversation_id, _user_message_id, parsed_context, _request_id = parse_generate_chat_reply_payload_reference(
        payload, content_store
    )
    assert conversation_id == 1
    assert parsed_context == realistic_context


def test_chat_reply_payload_rejects_malformed_reference():
    content_store = FakeContentStore()
    with pytest.raises(ValueError):
        parse_generate_chat_reply_payload_reference("generate_chat_reply:not-enough-parts", content_store)


def test_chat_reply_payload_rejects_reference_to_missing_stored_context():
    content_store = FakeContentStore()
    with pytest.raises(ValueError):
        parse_generate_chat_reply_payload_reference(
            "generate_chat_reply:1:1:request-1:never-saved.json", content_store
        )
