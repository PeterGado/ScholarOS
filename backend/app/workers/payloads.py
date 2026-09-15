"""Shared payload_reference formats for pipeline stages.

`Work Item.kind` is fixed to `pipeline_stage`/`domain_event` (04_Logical_Data_Model.md §3.20)
- the specific unit of work is encoded in `payload_reference` instead (Backend_Slice2_
Implementation_Plan.md §5's correction). One shared module so the enqueue site
(UploadResearchDocumentUseCase) and the consume site (the executor) never drift apart on the
format.
"""

import json
from uuid import uuid4

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
    draft_id: int, context: ContextAssemblyInput, *, request_id: str | None = None
) -> tuple[str, str]:
    """Serialize a server-created generation request into the existing Work Item payload.

    The context is deliberately snapshotted at enqueue time so a retry invokes the same
    Stage 5 request. The existing 512-character column is a hard boundary; callers must use
    a smaller context or introduce an explicitly authorized persistence change later.
    """
    request_id = request_id or uuid4().hex
    payload = {
        "draft_id": draft_id,
        "request_id": request_id,
        "context": _context_to_dict(context),
    }
    payload_reference = _GENERATE_DRAFT_VERSION_PREFIX + \
        json.dumps(payload, separators=(",", ":"), sort_keys=True)
    if len(payload_reference) > _MAX_PAYLOAD_REFERENCE_LENGTH:
        raise ValueError(
            "generation context exceeds the Work Item payload limit")
    return payload_reference, f"{_GENERATE_DRAFT_VERSION_PREFIX}{request_id}"


def parse_generate_draft_version_payload_reference(
    payload_reference: str,
) -> tuple[int, ContextAssemblyInput, str]:
    if not payload_reference.startswith(_GENERATE_DRAFT_VERSION_PREFIX):
        raise ValueError(
            f"Unrecognized payload reference: {payload_reference!r}")
    try:
        payload = json.loads(
            payload_reference[len(_GENERATE_DRAFT_VERSION_PREFIX):])
        draft_id = payload["draft_id"]
        request_id = payload["request_id"]
        context = _context_from_dict(payload["context"])
        if not isinstance(draft_id, int) or draft_id < 1 or not isinstance(request_id, str) or not request_id:
            raise ValueError
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Malformed generation payload reference: {payload_reference!r}") from exc
    return draft_id, context, request_id


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
