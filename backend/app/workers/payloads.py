"""Shared payload_reference format for the `process_document` pipeline stage.

`Work Item.kind` is fixed to `pipeline_stage`/`domain_event` (04_Logical_Data_Model.md §3.20)
- the specific unit of work is encoded in `payload_reference` instead (Backend_Slice2_
Implementation_Plan.md §5's correction). One shared module so the enqueue site
(UploadResearchDocumentUseCase) and the consume site (the executor) never drift apart on the
format.
"""

_PROCESS_DOCUMENT_PREFIX = "process_document:"


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
        raise ValueError(f"Unrecognized payload reference: {payload_reference!r}")
    return int(payload_reference[len(_PROCESS_DOCUMENT_PREFIX) :])
