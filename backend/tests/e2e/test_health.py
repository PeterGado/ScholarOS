from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database.session import build_sessionmaker
from app.main import app
from app.workers.enums import WorkItemKind, WorkItemState
from app.workers.models import WorkItem as WorkItemModel

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- GET /health/queue (2026-09-30, added after a production outage where the executor was
# stuck with no signal anywhere - see the "close it" follow-up work in this session) -----------


def _enqueue_work_item(db_engine, *, state: WorkItemState, created_at: datetime) -> None:
    session = build_sessionmaker(db_engine)()
    try:
        session.add(
            WorkItemModel(
                kind=WorkItemKind.PIPELINE_STAGE,
                state=state,
                payload_reference="process_document:1",
                idempotency_key="process_document:1",
                created_at=created_at,
            )
        )
        session.commit()
    finally:
        session.close()


def test_queue_health_is_healthy_when_empty(client, db_engine):
    response = client.get("/health/queue")

    assert response.status_code == 200
    assert response.json() == {"healthy": True, "oldest_unresolved_age_seconds": None}


def test_queue_health_is_healthy_for_a_recently_queued_item(client, db_engine):
    _enqueue_work_item(db_engine, state=WorkItemState.QUEUED, created_at=datetime.now(timezone.utc))

    response = client.get("/health/queue")

    assert response.status_code == 200
    body = response.json()
    assert body["healthy"] is True
    assert body["oldest_unresolved_age_seconds"] < 60


def test_queue_health_is_unhealthy_for_an_item_stuck_past_the_threshold(client, db_engine):
    stuck_since = datetime.now(timezone.utc) - timedelta(seconds=900)  # past the 600s default
    _enqueue_work_item(db_engine, state=WorkItemState.RUNNING, created_at=stuck_since)

    response = client.get("/health/queue")

    assert response.status_code == 503
    body = response.json()
    assert body["healthy"] is False
    assert body["oldest_unresolved_age_seconds"] > 600


def test_queue_health_ignores_terminal_items(client, db_engine):
    stuck_since = datetime.now(timezone.utc) - timedelta(seconds=900)
    _enqueue_work_item(db_engine, state=WorkItemState.SUCCEEDED, created_at=stuck_since)

    response = client.get("/health/queue")

    assert response.status_code == 200
    assert response.json() == {"healthy": True, "oldest_unresolved_age_seconds": None}
