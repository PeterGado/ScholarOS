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
