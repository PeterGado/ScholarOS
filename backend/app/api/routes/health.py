from datetime import UTC, datetime

import sentry_sdk
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.workers.repository import WorkItemRepository

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/queue")
def queue_health_check(response: Response, db: Session = Depends(get_db)) -> dict[str, object]:
    """Whether the Work Item queue is making progress - deliberately separate from `/health`
    (2026-09-30, added after a production outage where the executor silently stopped making
    progress for hours while `/health` kept passing the whole time, since the web server itself
    was never the problem). Not wired into Fly's own machine health check on purpose: unlike
    `/health`, an unhealthy result here doesn't mean restarting the machine would help, so it's
    meant for an external monitor/alert to poll instead. Also reports to Sentry when unhealthy,
    the same signal by a second route, for anyone watching Sentry rather than polling this.
    """
    threshold = get_settings().queue_stale_threshold_seconds
    oldest_created_at = WorkItemRepository(db).oldest_unresolved_created_at()

    if oldest_created_at is None:
        return {"healthy": True, "oldest_unresolved_age_seconds": None}

    # SQLite (local dev/test) returns a naive datetime even though every value written here is
    # already UTC (see WorkItem.created_at's own default) - Postgres returns it tz-aware already,
    # so this is a no-op there. Without it, this subtraction raises on SQLite.
    if oldest_created_at.tzinfo is None:
        oldest_created_at = oldest_created_at.replace(tzinfo=UTC)
    age_seconds = (datetime.now(UTC) - oldest_created_at).total_seconds()
    healthy = age_seconds <= threshold
    if not healthy:
        response.status_code = 503
        sentry_sdk.capture_message(
            f"Work item queue has an unresolved item {age_seconds:.0f}s old "
            f"(threshold {threshold}s) - the executor may be stuck.",
            level="error",
        )
    return {"healthy": healthy, "oldest_unresolved_age_seconds": age_seconds}
