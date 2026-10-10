import asyncio
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime

import sentry_sdk
from sqlalchemy.orm import Session

from app.workers.repository import WorkItemRepository

logger = logging.getLogger(__name__)


def check_queue_health(db: Session, *, stale_threshold_seconds: int) -> tuple[bool, float | None]:
    """Returns (healthy, oldest_unresolved_age_seconds). Reports to Sentry when unhealthy.

    Shared by the `/health/queue` route (app.api.routes.health) and QueueHealthMonitor below,
    extracted here (2026-10-10) so the same staleness check can run both on demand (an external
    monitor polling the route) and periodically from inside this process, without duplicating
    the Sentry-reporting logic between them.
    """
    oldest_created_at = WorkItemRepository(db).oldest_unresolved_created_at()
    if oldest_created_at is None:
        return True, None

    # SQLite (local dev/test) returns a naive datetime even though every value written here is
    # already UTC (see WorkItem.created_at's own default) - Postgres returns it tz-aware already,
    # so this is a no-op there. Without it, this subtraction raises on SQLite.
    if oldest_created_at.tzinfo is None:
        oldest_created_at = oldest_created_at.replace(tzinfo=UTC)
    age_seconds = (datetime.now(UTC) - oldest_created_at).total_seconds()
    healthy = age_seconds <= stale_threshold_seconds
    if not healthy:
        sentry_sdk.capture_message(
            f"Work item queue has an unresolved item {age_seconds:.0f}s old "
            f"(threshold {stale_threshold_seconds}s) - the executor may be stuck.",
            level="error",
        )
    return healthy, age_seconds


class QueueHealthMonitor:
    """Periodically self-checks the Work Item queue for staleness from inside this same process
    (2026-10-10, production-readiness pass: "logging and monitoring - alert setup for critical
    failures"). `/health/queue` already existed but nothing ever polled it, so a stuck-but-still-
    running executor - exactly the shape of the 2026-09-30 "stuck on Thinking" outage, where the
    web server kept answering fine while the executor silently stopped making progress - would
    go unnoticed until a user complained. This closes that specific gap without any new external
    infrastructure or a Fly health-check wired to restart the machine (deliberately not done -
    see queue_health_check's own docstring on why an unhealthy queue doesn't mean a restart
    would help).

    Scope, stated honestly: this can only ever observe "the process is alive but the queue isn't
    moving". If the whole process dies, nothing inside it can report that - genuine external
    uptime monitoring (polling `/health/queue` from outside) is still the only way to catch that
    case, and remains a real, separate gap.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        stale_threshold_seconds: int,
        check_interval_seconds: float = 60.0,
    ) -> None:
        self._session_factory = session_factory
        self._stale_threshold_seconds = stale_threshold_seconds
        self._check_interval_seconds = check_interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="queue-health-monitor", daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            await asyncio.to_thread(self._thread.join)

    def _run(self) -> None:
        # wait() returns True only once stop() sets the event - looping on "not stopped" means
        # a check runs every interval until shutdown, with no busy-polling in between.
        while not self._stop_event.wait(timeout=self._check_interval_seconds):
            session = self._session_factory()
            try:
                check_queue_health(session, stale_threshold_seconds=self._stale_threshold_seconds)
            except Exception:
                logger.exception("Queue health monitor check failed")
            finally:
                session.close()
