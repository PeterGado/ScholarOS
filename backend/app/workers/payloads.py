"""Shared payload_reference formats for pipeline stages.

`Work Item.kind` is fixed to `pipeline_stage`/`domain_event` (04_Logical_Data_Model.md §3.20)
- the specific unit of work is encoded in `payload_reference` instead (Backend_Slice2_
Implementation_Plan.md §5's correction). One shared module so the enqueue site
(UploadResearchDocumentUseCase) and the consume site (the executor) never drift apart on the
format.

`payload_reference` is documented as "Short Text - reference to the work payload"
(04_Logical_Data_Model.md §3.20), the same logical type as `ResearchDocument.
content_reference` (§3.4) - a pointer, not the payload itself. `build_process_document_
payload_reference` already follows that: `process_document:<id>` is a genuine reference.
`build_generate_draft_version_payload_reference` follows the same pattern: the (potentially
large - evidence chunk content, style signals, memory) `ContextAssemblyInput` is written to
the existing content-addressed `ContentStore` (the same abstraction and the same object-store
category `UploadResearchDocumentUseCase` already writes into, ADR-004 §5) and only a short
reference to it is embedded in `payload_reference`, exactly mirroring `ResearchDocument.
content_reference`. An earlier version of this function inlined the full serialized context
directly into `payload_reference` and rejected anything over 512 characters - workable only
for near-empty contexts, since Context Assembly's own default budget is 12,000 characters
across up to 10 evidence chunks. Found and fixed before Stage 7; see the review that flagged
it for the full reasoning.
"""

import json
from uuid import uuid4

from app.modules.document.domain.ports import ContentStore
from app.modules.writing.domain.context_assembly import (
    ContextAssemblyInput,
    ContextEvidence,
    ContextEvidenceSource,
    ContextMemory,
    ContextStyleSignal,
)
from app.modules.writing.domain.enums import MemoryRecordType, ProfileCharacteristicType

_PROCESS_DOCUMENT_PREFIX = "process_document:"
_GENERATE_DRAFT_VERSION_PREFIX = "generate_draft_version:"
# No longer sized against a serialized context (see module docstring) - this now only bounds
# the reference itself (draft_id + request_id + content-store key), which is always small and
# of roughly fixed size regardless of context size. Kept as a defensive assertion, not a
# routine limitation.
_MAX_PAYLOAD_REFERENCE_LENGTH = 512


def build_process_document_payload_reference(document_id: int) -> str:
    return f"{_PROCESS_DOCUMENT_PREFIX}{document_id}"


def build_process_document_idempotency_key(document_id: int) -> str:
    """Same shape as the payload reference - guarantees at most one Work Item is ever
    enqueued per document (the idempotency_key column is unique), which also means "does a
    Work Item already exist for this document" needs no separate query.
    """
    return build_process_document_payload_reference(document_id)


def parse_process_document_payload_reference(payload_reference: str) -> int:
    if not payload_reference.startswith(_PROCESS_DOCUMENT_PREFIX):
        raise ValueError(
            f"Unrecognized payload reference: {payload_reference!r}")
    return int(payload_reference[len(_PROCESS_DOCUMENT_PREFIX):])


def build_generate_draft_version_payload_reference(
    draft_id: int,
    context: ContextAssemblyInput,
    content_store: ContentStore,
    *,
    request_id: str | None = None,
    message_id: int | None = None,
) -> tuple[str, str]:
    """Persist a server-created generation request's context to the content store and embed
    only a short reference to it in the Work Item payload (see module docstring for why).

    The context is deliberately snapshotted at enqueue time (written once, content-addressed)
    so a retry re-reads the identical Stage 5 request rather than a possibly-changed one.

    `message_id` (added resolving the Stage 8 instructions-contract finding) identifies the
    Draft-scoped Conversation Message that carried these instructions
    (RequestDraftGenerationUseCase), so the executor can link it to the resulting Draft Version
    via Message Context Link once generation succeeds. Optional - `None` for any caller that
    does not go through that use case (e.g. a direct Stage 6 test), encoded as an empty segment.
    """
    request_id = request_id or uuid4().hex
    context_json = json.dumps(_context_to_dict(context), separators=(",", ":"), sort_keys=True)
    context_reference = content_store.save(context_json.encode("utf-8"), extension="json")

    message_segment = str(message_id) if message_id is not None else ""
    payload_reference = (
        f"{_GENERATE_DRAFT_VERSION_PREFIX}{draft_id}:{request_id}:{context_reference}:{message_segment}"
    )
    if len(payload_reference) > _MAX_PAYLOAD_REFERENCE_LENGTH:
        raise ValueError("generate_draft_version payload reference unexpectedly exceeds the Work Item column limit")
    return payload_reference, f"{_GENERATE_DRAFT_VERSION_PREFIX}{request_id}"


def parse_generate_draft_version_payload_reference(
    payload_reference: str, content_store: ContentStore
) -> tuple[int, ContextAssemblyInput, str, int | None]:
    if not payload_reference.startswith(_GENERATE_DRAFT_VERSION_PREFIX):
        raise ValueError(f"Unrecognized payload reference: {payload_reference!r}")
    try:
        remainder = payload_reference[len(_GENERATE_DRAFT_VERSION_PREFIX):]
        draft_id_text, request_id, context_reference, message_segment = remainder.split(":", 3)
        draft_id = int(draft_id_text)
        if draft_id < 1 or not request_id or not context_reference:
            raise ValueError
        message_id = int(message_segment) if message_segment else None
        context_json = content_store.read(context_reference)
        context = _context_from_dict(json.loads(context_json))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Malformed generation payload reference: {payload_reference!r}") from exc
    return draft_id, context, request_id, message_id


def _context_to_dict(context: ContextAssemblyInput) -> dict:
    return {
        "topic": context.topic,
        "instructions": context.instructions,
        "max_characters": context.max_characters,
        "max_evidence": context.max_evidence,
        "evidence": [
            {
                "chunk_id": item.chunk_id,
                "content": item.content,
                "summary": item.summary,
                "score": item.score,
                "sources": [
                    {"document_id": source.document_id,
                        "document_title": source.document_title}
                    for source in item.sources
                ],
            }
            for item in context.evidence
        ],
        "style_signals": [
            {
                "characteristic_type": item.characteristic_type.value,
                "signal": item.signal,
                "confidence": item.confidence,
            }
            for item in context.style_signals
        ],
        "memories": [
            {"record_type": item.record_type.value,
                "content": item.content, "rationale": item.rationale}
            for item in context.memories
        ],
    }


def _context_from_dict(payload: dict) -> ContextAssemblyInput:
    if not isinstance(payload, dict):
        raise ValueError
    return ContextAssemblyInput(
        topic=payload["topic"],
        instructions=payload["instructions"],
        max_characters=payload["max_characters"],
        max_evidence=payload["max_evidence"],
        evidence=tuple(
            ContextEvidence(
                chunk_id=item["chunk_id"],
                content=item["content"],
                summary=item["summary"],
                score=item["score"],
                sources=tuple(
                    ContextEvidenceSource(
                        document_id=source["document_id"], document_title=source["document_title"]
                    )
                    for source in item.get("sources", [])
                ),
            )
            for item in payload.get("evidence", [])
        ),
        style_signals=tuple(
            ContextStyleSignal(
                characteristic_type=ProfileCharacteristicType(
                    item["characteristic_type"]),
                signal=item["signal"],
                confidence=item["confidence"],
            )
            for item in payload.get("style_signals", [])
        ),
        memories=tuple(
            ContextMemory(
                record_type=MemoryRecordType(item["record_type"]),
                content=item["content"],
                rationale=item["rationale"],
            )
            for item in payload.get("memories", [])
        ),
    )
