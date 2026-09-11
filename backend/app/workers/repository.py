from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.workers.entities import WorkItem
from app.workers.enums import WorkItemKind, WorkItemState
from app.workers.models import WorkItem as WorkItemModel

DEFAULT_MAX_ATTEMPTS = 3


class WorkItemRepository:
    """Owns every SQLAlchemy detail for Work Item persistence (ADR-006's durable outbox).
    Concrete, not behind a Protocol/ABC split - `app/workers/` is an infrastructure/
    orchestration-boundary package like `app/auth/`, not a `modules/`-style bounded context
    with its own dependency-direction test.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(self, *, kind: WorkItemKind, payload_reference: str, idempotency_key: str) -> WorkItem:
        row = WorkItemModel(kind=kind, payload_reference=payload_reference, idempotency_key=idempotency_key)
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def claim_next_queued(self) -> WorkItem | None:
        """Claims the oldest queued item, transitioning it to `running`. Single-writer-safe
        for the MVP's one in-process executor (ADR-006 Decision 3); not safe against
        multiple concurrent claimers - true concurrency safety is the durable-broker
        extraction path (ADR-006 Decision 4), not an MVP requirement.
        """
        row = (
            self._session.query(WorkItemModel)
            .filter_by(state=WorkItemState.QUEUED)
            .order_by(WorkItemModel.work_item_id)
            .first()
        )
        if row is None:
            return None
        row.state = WorkItemState.RUNNING
        row.executed_at = datetime.now(timezone.utc)
        self._session.flush()
        return self._to_domain(row)

    def mark_succeeded(self, work_item_id: int) -> None:
        row = self._session.get(WorkItemModel, work_item_id)
        row.state = WorkItemState.SUCCEEDED
        row.completed_at = datetime.now(timezone.utc)
        self._session.flush()

    def mark_failed(self, work_item_id: int, *, error: str, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> WorkItem:
        """Bounded retry (ADR-006 Decision 5): `failed -> queued` while attempts remain,
        `failed` (terminal) once `max_attempts` is reached. Returns the updated item so the
        caller can tell which outcome occurred without a second query.
        """
        row = self._session.get(WorkItemModel, work_item_id)
        row.attempts += 1
        row.last_error = error
        if row.attempts < max_attempts:
            row.state = WorkItemState.QUEUED
        else:
            row.state = WorkItemState.FAILED
            row.completed_at = datetime.now(timezone.utc)
        self._session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: WorkItemModel) -> WorkItem:
        return WorkItem(
            work_item_id=row.work_item_id,
            kind=row.kind,
            state=row.state,
            payload_reference=row.payload_reference,
            idempotency_key=row.idempotency_key,
            attempts=row.attempts,
            last_error=row.last_error,
            created_at=row.created_at,
            executed_at=row.executed_at,
            completed_at=row.completed_at,
        )
