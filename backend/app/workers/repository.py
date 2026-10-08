from datetime import UTC, datetime, timedelta

from sqlalchemy import text
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

    def oldest_unresolved_created_at(self) -> datetime | None:
        """The `created_at` of the oldest Work Item still in `queued` or `running` - the queue
        health check's only real signal (2026-09-30, added after a production outage): a
        genuinely healthy queue never has an unresolved item older than a few tens of seconds,
        since every kind of work here (an AI generation call, document processing) completes or
        reaches a terminal `failed` state well within that. `created_at`, not `executed_at`, so a
        long-`queued` item (never even claimed) is caught the same as a long-`running` one -
        `requeue_stale_running` already handles the latter at executor startup, but only once, and
        this needs to keep noticing regardless of *why* an item is stuck. Returns None when the
        queue is fully drained (nothing to report).
        """
        row = (
            self._session.query(WorkItemModel)
            .filter(WorkItemModel.state.in_([WorkItemState.QUEUED, WorkItemState.RUNNING]))
            .order_by(WorkItemModel.created_at.asc())
            .first()
        )
        return row.created_at if row is not None else None

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

    def cancel_queued_by_payload_reference(self, payload_reference: str) -> WorkItem | None:
        """Terminally fails a still-`queued` Work Item for a payload_reference whose underlying
        record is about to disappear (e.g. a Research Document being deleted while its
        processing item hasn't been claimed yet) - a queued item that outlives the thing it
        refers to can never succeed no matter how many times it's retried, and until 2026-09-30
        an orphan like this reached the executor, crashed on a lookup of the now-gone record,
        and (since that crash happened before any outcome was recorded) had its claim silently
        rolled back - so the *same* oldest queued item was reclaimed and crashed again on every
        poll, forever, starving every other queued item behind it. Only `queued` items are
        touched: a `running` one is being actively processed by the executor right now and must
        run to completion untouched; this codebase's own delete/cancel call sites never race
        that state (a Research Document can only be deleted while `pending`/`failed`, never
        while its item is `running`, e.g. `DeleteResearchDocumentUseCase`).
        """
        row = (
            self._session.query(WorkItemModel)
            .filter_by(payload_reference=payload_reference, state=WorkItemState.QUEUED)
            .order_by(WorkItemModel.work_item_id.desc())
            .first()
        )
        if row is None:
            return None
        row.state = WorkItemState.FAILED
        row.last_error = "Cancelled: the record this work item refers to no longer exists."
        row.completed_at = datetime.now(UTC)
        self._session.flush()
        return self._to_domain(row)

    def cancel_queued_by_payload_prefix(self, payload_reference_prefix: str) -> int:
        """Terminally fails every still-`queued` Work Item whose payload_reference starts with
        the given prefix - the chat-reply counterpart to `cancel_queued_by_payload_reference`
        (an exact match isn't possible here: a chat reply's payload_reference also encodes its
        message_id/request_id/context reference, not just the conversation it belongs to, so a
        deleted conversation's queued replies - normally at most one, but nothing here enforces
        that - are found by prefix instead; see `build_generate_chat_reply_payload_reference_
        prefix`'s own docstring for why the prefix must include its trailing delimiter). Only
        `queued` items are touched, for the same reason as `cancel_queued_by_payload_reference`:
        a `running` item is being actively processed right now, and `GenerateConversationReplyUse
        Case.execute` already checks for a deleted conversation itself at the top of its own run,
        so a running item completing after its conversation was deleted is already handled
        correctly without touching it here.
        """
        rows = (
            self._session.query(WorkItemModel)
            .filter(
                WorkItemModel.state == WorkItemState.QUEUED,
                WorkItemModel.payload_reference.like(f"{payload_reference_prefix}%"),
            )
            .all()
        )
        now = datetime.now(UTC)
        for row in rows:
            row.state = WorkItemState.FAILED
            row.last_error = "Cancelled: the record this work item refers to no longer exists."
            row.completed_at = now
        self._session.flush()
        return len(rows)

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
        """Claims the oldest queued item, transitioning it to `running`.

        On Postgres, uses a single atomic `UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP
        LOCKED) RETURNING` statement (2026-09-30, concurrent-load planning) - `SKIP LOCKED`
        makes a second concurrent claimer (the executor now runs `work_item_worker_count`
        threads) physically skip a row another claimer already holds the lock on, rather than
        block on it or re-select it, so two callers can never both come back with the same row.
        One round trip, and no ORM identity-map subtlety to keep verifying as this method's
        callers change.

        SQLite (tests/local dev) keeps the previous simple SELECT + mutate + flush form
        unchanged: it doesn't support `SKIP LOCKED`, and has no concurrent claimers to guard
        against in the first place (this codebase's tests never call this method from more than
        one thread against a SQLite session).
        """
        if self._session.get_bind().dialect.name == "postgresql":
            # `state`/`kind` bound as parameters, never inlined string literals: the Enum
            # columns are `native_enum=False`, which persists the Python member *name*
            # (`"QUEUED"`), not `.value` (`"queued"`) - binding `WorkItemState.RUNNING.name`
            # keeps this correct even if that storage detail is ever revisited, instead of a
            # hand-typed literal silently drifting out of sync with it.
            row = self._session.execute(
                text(
                    """
                    UPDATE work_items
                    SET state = :running_state, executed_at = now()
                    WHERE work_item_id = (
                        SELECT work_item_id FROM work_items
                        WHERE state = :queued_state
                        ORDER BY work_item_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    RETURNING work_item_id, kind, state, payload_reference, idempotency_key,
                              attempts, last_error, created_at, executed_at, completed_at
                    """
                ),
                {"running_state": WorkItemState.RUNNING.name, "queued_state": WorkItemState.QUEUED.name},
            ).first()
            return self._to_domain_from_row(row) if row is not None else None

        row = (
            self._session.query(WorkItemModel)
            .filter_by(state=WorkItemState.QUEUED)
            .order_by(WorkItemModel.work_item_id)
            .first()
        )
        if row is None:
            return None
        row.state = WorkItemState.RUNNING
        row.executed_at = datetime.now(UTC)
        self._session.flush()
        return self._to_domain(row)

    def mark_succeeded(self, work_item_id: int) -> None:
        row = self._session.get(WorkItemModel, work_item_id)
        row.state = WorkItemState.SUCCEEDED
        row.completed_at = datetime.now(UTC)
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
            row.completed_at = datetime.now(UTC)
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

        On Postgres, locks the matching rows with `FOR UPDATE SKIP LOCKED` (2026-09-30,
        concurrent-load planning) so two processes recovering stale items at the same moment
        (e.g. two Fly machines restarting together) can't both grab the same row - not a
        concern yet with this rollout's single-machine design, but cheap to make correct now
        while `claim_next_queued` gets the same treatment for the same underlying reason.
        """
        threshold = datetime.now(UTC) - stale_after
        query = self._session.query(WorkItemModel).filter(
            WorkItemModel.state == WorkItemState.RUNNING, WorkItemModel.executed_at < threshold
        )
        if self._session.get_bind().dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        rows = query.all()
        for row in rows:
            row.attempts += 1
            row.last_error = (
                "Recovered stale running Work Item (executor restarted before recording an outcome)."
            )
            if row.attempts < max_attempts:
                row.state = WorkItemState.QUEUED
            else:
                row.state = WorkItemState.FAILED
                row.completed_at = datetime.now(UTC)
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

    @staticmethod
    def _to_domain_from_row(row) -> WorkItem:
        """Same mapping as `_to_domain`, for a raw `Row` from `claim_next_queued`'s Postgres
        `RETURNING` statement instead of an ORM `WorkItemModel` instance - `kind`/`state` come
        back as the raw persisted strings (the columns are `native_enum=False`, which persists
        the Python enum member's *name*, e.g. `"QUEUED"`, not `.value`) rather than enum members,
        so they're looked up by name here, not by value.
        """
        return WorkItem(
            work_item_id=row.work_item_id,
            kind=WorkItemKind[row.kind],
            state=WorkItemState[row.state],
            payload_reference=row.payload_reference,
            idempotency_key=row.idempotency_key,
            attempts=row.attempts,
            last_error=row.last_error,
            created_at=row.created_at,
            executed_at=row.executed_at,
            completed_at=row.completed_at,
        )
