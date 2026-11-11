from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.workers.enums import WorkItemKind, WorkItemState
from app.workers.health import check_queue_health
from app.workers.models import WorkItem


@pytest.fixture()
def session_factory(tmp_path):
    db_path = tmp_path / "workers_health_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    factory = build_sessionmaker(engine)
    try:
        yield factory
    finally:
        engine.dispose()


def _insert_work_item(session, *, created_at: datetime, state: WorkItemState = WorkItemState.QUEUED) -> None:
    session.add(
        WorkItem(
            kind=WorkItemKind.PIPELINE_STAGE,
            state=state,
            payload_reference="process_document:1",
            idempotency_key="test-key",
            created_at=created_at,
        )
    )
    session.commit()


def test_empty_queue_is_healthy(session_factory):
    session = session_factory()
    try:
        healthy, age = check_queue_health(session, stale_threshold_seconds=600)
    finally:
        session.close()
    assert healthy is True
    assert age is None


def test_a_fresh_queued_item_is_healthy(session_factory):
    session = session_factory()
    try:
        _insert_work_item(session, created_at=datetime.now(UTC))
        healthy, age = check_queue_health(session, stale_threshold_seconds=600)
    finally:
        session.close()
    assert healthy is True
    assert age is not None
    assert age < 60


def test_a_stale_queued_item_is_unhealthy_and_reports_to_sentry(session_factory):
    session = session_factory()
    try:
        _insert_work_item(session, created_at=datetime.now(UTC) - timedelta(seconds=700))
        with patch("app.workers.health.sentry_sdk.capture_message") as capture:
            healthy, age = check_queue_health(session, stale_threshold_seconds=600)
    finally:
        session.close()
    assert healthy is False
    assert age is not None and age >= 700
    capture.assert_called_once()
    assert capture.call_args.kwargs["level"] == "error"


def test_a_completed_item_never_counts_toward_staleness(session_factory):
    session = session_factory()
    try:
        _insert_work_item(
            session,
            created_at=datetime.now(UTC) - timedelta(seconds=700),
            state=WorkItemState.SUCCEEDED,
        )
        with patch("app.workers.health.sentry_sdk.capture_message") as capture:
            healthy, age = check_queue_health(session, stale_threshold_seconds=600)
    finally:
        session.close()
    assert healthy is True
    assert age is None
    capture.assert_not_called()
