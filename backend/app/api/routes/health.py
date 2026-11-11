from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.workers.health import check_queue_health

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
    meant for an external monitor/alert to poll instead.

    The actual staleness check lives in app.workers.health.check_queue_health (2026-10-10),
    shared with QueueHealthMonitor - a periodic in-process self-check started alongside the
    executor (app.main's lifespan) so the same signal also reaches Sentry without depending on
    anything external polling this route.
    """
    threshold = get_settings().queue_stale_threshold_seconds
    healthy, age_seconds = check_queue_health(db, stale_threshold_seconds=threshold)
    if not healthy:
        response.status_code = 503
    return {"healthy": healthy, "oldest_unresolved_age_seconds": age_seconds}
