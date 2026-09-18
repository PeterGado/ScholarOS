from datetime import datetime, timedelta, timezone

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

    def get_by_payload_reference(self, payload_reference: str) -> WorkItem | None:
        """The most recent Work Item for a given payload_reference (e.g. `process_document:7`) -
        used to surface *why* a document's processing terminally failed, without the document
        module owning any Work Item persistence itself.
        """
        row = (
            self._session.query(WorkItemModel)
            .filter_by(payload_reference=payload_reference)
            .order_by(WorkItemModel.work_item_id.desc())
            .first()
        )
        return self._to_domain(row) if row is not None else None

    def get_by_id(self, work_item_id: int) -> WorkItem | None:
        """Looked up directly by primary key - used where a caller already holds a specific
        work_item_id from an earlier enqueue response (e.g. chat reply status polling) rather
        than re-deriving it from a payload_reference.
        """
        row = self._session.get(WorkItemModel, work_item_id)
        return self._to_domain(row) if row is not None else None

    def requeue_failed_by_payload_reference(self, payload_reference: str) -> WorkItem | None:
        """Resets an already-terminal `failed` Work Item back to `queued` for a fresh bounded
        retry - used by "Retry" on a failed document. Resets the existing row rather than
        enqueuing a new one: `idempotency_key` is unique per payload_reference, so a second
        `enqueue` call for the same document would violate that constraint. Returns None if no
        `failed` item matches (nothing to retry).
        """
        row = (
            self._session.query(WorkItemModel)
            .filter_by(payload_reference=payload_reference, state=WorkItemState.FAILED)
            .order_by(WorkItemModel.work_item_id.desc())
            .first()
        )
        if row is None:
            return None
        row.state = WorkItemState.QUEUED
        row.attempts = 0
        row.last_error = None
        row.executed_at = None
        row.completed_at = None
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

    def requeue_stale_running(
        self, *, stale_after: timedelta, max_attempts: int = DEFAULT_MAX_ATTEMPTS
    ) -> int:
        """Recovers Work Items stuck in `running` because the process that claimed them
        (the MVP's single in-process executor, ADR-006 Decision 3) crashed or was killed
        before recording an outcome. `claim_next_queued` only ever claims `state=queued` rows -
        nothing else in this module ever moves a `running` row forward, so absent this method a
        crash mid-processing left the item stuck forever, never retried (found during Project
        Writing Stage 8 validation; general to every Work Item kind, not Writing-specific).

        Intended to be called once, at executor startup, before polling begins - never mid-poll,
        since a `running` row may simply belong to work the current process itself is still
        doing (`executed_at` alone can't distinguish "still running" from "crashed while
        running" without a time threshold, hence `stale_after`). Reuses `mark_failed`'s own
        bounded-retry rule (attempts vs. `max_attempts`) so a poison item that keeps crashing
        its worker still terminates in `failed` rather than looping forever.

        Returns the number of rows recovered (requeued or terminally failed).
        """
        threshold = datetime.now(timezone.utc) - stale_after
        rows = (
            self._session.query(WorkItemModel)
            .filter(WorkItemModel.state == WorkItemState.RUNNING, WorkItemModel.executed_at < threshold)
            .all()
        )
        for row in rows:
            row.attempts += 1
            row.last_error = (
                "Recovered stale running Work Item (executor restarted before recording an outcome)."
            )
            if row.attempts < max_attempts:
                row.state = WorkItemState.QUEUED
            else:
                row.state = WorkItemState.FAILED
                row.completed_at = datetime.now(timezone.utc)
        self._session.flush()
        return len(rows)

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
