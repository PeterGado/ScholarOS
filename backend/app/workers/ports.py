from typing import Protocol

from app.workers.entities import WorkItem
from app.workers.enums import WorkItemKind


class WorkItemEnqueuer(Protocol):
    """The only Work Item capability callers outside `app/workers/` itself need - enqueueing.
    `claim_next_queued`/`mark_succeeded`/`mark_failed` are the executor's own concern and stay
    on the concrete `WorkItemRepository`. Application-layer code (e.g.
    `UploadResearchDocumentUseCase`) depends on this Protocol, never on the concrete
    repository directly - the same dependency-inversion pattern `ContentStore` already uses.
    """

    def enqueue(self, *, kind: WorkItemKind, payload_reference: str, idempotency_key: str) -> WorkItem: ...


class WorkItemOutcomeLookup(Protocol):
    """A second narrow capability: reading a Work Item's terminal outcome and retrying a failed
    one, both scoped to a payload_reference - what the document module needs to show *why* a
    document's processing failed and to let the user retry it, without owning any Work Item
    persistence itself. Mirrors `WorkItemEnqueuer`'s own narrow-capability pattern.
    """

    def get_by_payload_reference(self, payload_reference: str) -> WorkItem | None: ...

    def get_by_id(self, work_item_id: int) -> WorkItem | None: ...

    def requeue_failed_by_payload_reference(self, payload_reference: str) -> WorkItem | None: ...
