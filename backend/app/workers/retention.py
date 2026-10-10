import asyncio
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ai.models import AiUsageRecord
from app.core.rate_limit_models import RateLimitCounter
from app.workers.models import WorkItem, WorkItemState

logger = logging.getLogger(__name__)


def cleanup_expired_data(
    db: Session, *, usage_retention: timedelta, work_item_retention: timedelta
) -> dict[str, int]:
    """Deletes aged-out rows from the three purely operational/bookkeeping tables that
    otherwise grow forever (2026-10-10, production-readiness pass): the AI usage ledger, the
    rate-limiter's counter table, and terminal (succeeded/failed) Work Items.

    Deliberately never touches anything that represents what the AI knows or has produced for
    a user - KnowledgeChunk, MemoryRecord, Message, ResearchDocument, and every other content
    table are completely out of scope and untouched by this function; this is the explicit
    distinction the project owner asked for when this was scoped.

    Returns a count per table, for logging and tests - not used by callers to decide anything.
    """
    usage_cutoff = datetime.now(UTC) - usage_retention
    work_item_cutoff = datetime.now(UTC) - work_item_retention
    # rate_limit_counters.expires_at is a Unix epoch float (RateLimitCounter's own docstring) -
    # not a datetime column, so the cutoff is computed the same way but compared as a float.
    rate_limit_cutoff = usage_cutoff.timestamp()

    # mypy sees Session.execute's return type as the generic Result[*tuple[Any, ...]], which
    # has no statically-declared .rowcount - only CursorResult (what a DELETE actually returns
    # at runtime) does. Same gap app.core.rate_limit_storage avoids by calling
    # Connection.execute(text(...)) directly instead of Session.execute(delete(...)).
    usage_deleted = db.execute(
        delete(AiUsageRecord).where(AiUsageRecord.recorded_at < usage_cutoff)
    ).rowcount  # type: ignore[attr-defined]
    rate_limit_deleted = db.execute(
        delete(RateLimitCounter).where(RateLimitCounter.expires_at < rate_limit_cutoff)
    ).rowcount  # type: ignore[attr-defined]
    work_items_deleted = db.execute(
        delete(WorkItem).where(
            WorkItem.state.in_((WorkItemState.SUCCEEDED, WorkItemState.FAILED)),
            WorkItem.completed_at < work_item_cutoff,
        )
    ).rowcount  # type: ignore[attr-defined]
    db.commit()

    return {
        "ai_usage_records": usage_deleted,
        "rate_limit_counters": rate_limit_deleted,
        "work_items": work_items_deleted,
    }


class DataRetentionJob:
    """Periodically purges aged-out operational bookkeeping rows from inside this same process
    (2026-10-10, production-readiness pass), mirroring QueueHealthMonitor's own thread/stop-
    event shape (app.workers.health) rather than introducing a new scheduling mechanism.

    Runs once per `check_interval_seconds` (default: daily) rather than on every request or
    continuously - this is routine housekeeping, not latency-sensitive, and a day's growth in
    any of the three tables it targets is negligible at this project's scale.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        usage_retention: timedelta,
        work_item_retention: timedelta,
        check_interval_seconds: float = 86400.0,
    ) -> None:
        self._session_factory = session_factory
        self._usage_retention = usage_retention
        self._work_item_retention = work_item_retention
        self._check_interval_seconds = check_interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="data-retention-job", daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            await asyncio.to_thread(self._thread.join)

    def _run(self) -> None:
        while not self._stop_event.wait(timeout=self._check_interval_seconds):
            session = self._session_factory()
            try:
                deleted = cleanup_expired_data(
                    session,
                    usage_retention=self._usage_retention,
                    work_item_retention=self._work_item_retention,
                )
                if any(deleted.values()):
                    logger.info("Data retention cleanup deleted rows: %s", deleted)
            except Exception:
                session.rollback()
                logger.exception("Data retention cleanup failed")
            finally:
                session.close()
