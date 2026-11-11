import time
from datetime import UTC, datetime, timedelta

import pytest

from app.ai.models import AiUsageRecord
from app.core.rate_limit_models import RateLimitCounter
from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.workers.enums import WorkItemKind, WorkItemState
from app.workers.models import WorkItem
from app.workers.retention import cleanup_expired_data

USAGE_RETENTION = timedelta(days=90)
WORK_ITEM_RETENTION = timedelta(days=30)


@pytest.fixture()
def session_factory(tmp_path):
    db_path = tmp_path / "workers_retention_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    factory = build_sessionmaker(engine)
    try:
        yield factory
    finally:
        engine.dispose()


def _insert_user(session) -> int:
    user = User(username="retention-test-user")
    session.add(user)
    session.commit()
    return user.user_id


def _insert_usage_record(session, *, user_id: int, recorded_at: datetime) -> None:
    session.add(AiUsageRecord(user_id=user_id, tokens=100, recorded_at=recorded_at))
    session.commit()


def _insert_rate_limit_counter(session, *, key: str, expires_at: float) -> None:
    session.add(RateLimitCounter(key=key, counter=1, expires_at=expires_at))
    session.commit()


def _insert_work_item(session, *, state: WorkItemState, completed_at: datetime | None, idempotency_key: str) -> None:
    session.add(
        WorkItem(
            kind=WorkItemKind.PIPELINE_STAGE,
            state=state,
            payload_reference="process_document:1",
            idempotency_key=idempotency_key,
            created_at=datetime.now(UTC) - timedelta(days=200),
            completed_at=completed_at,
        )
    )
    session.commit()


def test_old_usage_records_are_deleted_recent_ones_kept(session_factory):
    session = session_factory()
    try:
        user_id = _insert_user(session)
        _insert_usage_record(session, user_id=user_id, recorded_at=datetime.now(UTC) - timedelta(days=100))
        _insert_usage_record(session, user_id=user_id, recorded_at=datetime.now(UTC) - timedelta(days=10))

        deleted = cleanup_expired_data(
            session, usage_retention=USAGE_RETENTION, work_item_retention=WORK_ITEM_RETENTION
        )

        remaining = session.query(AiUsageRecord).all()
    finally:
        session.close()

    assert deleted["ai_usage_records"] == 1
    assert len(remaining) == 1


def test_old_rate_limit_counters_are_deleted_recent_ones_kept(session_factory):
    session = session_factory()
    try:
        now = time.time()
        _insert_rate_limit_counter(session, key="old-key", expires_at=now - timedelta(days=100).total_seconds())
        _insert_rate_limit_counter(session, key="recent-key", expires_at=now - timedelta(days=10).total_seconds())

        deleted = cleanup_expired_data(
            session, usage_retention=USAGE_RETENTION, work_item_retention=WORK_ITEM_RETENTION
        )

        remaining = session.query(RateLimitCounter).all()
    finally:
        session.close()

    assert deleted["rate_limit_counters"] == 1
    assert [r.key for r in remaining] == ["recent-key"]


def test_old_terminal_work_items_are_deleted_queued_and_running_never_are(session_factory):
    session = session_factory()
    try:
        old_completed_at = datetime.now(UTC) - timedelta(days=60)
        recent_completed_at = datetime.now(UTC) - timedelta(days=5)
        _insert_work_item(session, state=WorkItemState.SUCCEEDED, completed_at=old_completed_at, idempotency_key="k1")
        _insert_work_item(session, state=WorkItemState.FAILED, completed_at=old_completed_at, idempotency_key="k2")
        _insert_work_item(
            session, state=WorkItemState.SUCCEEDED, completed_at=recent_completed_at, idempotency_key="k3"
        )
        # Old but never terminal - must survive regardless of age; a stuck/queued item is a
        # health-monitor concern (app.workers.health), never something retention should delete.
        _insert_work_item(session, state=WorkItemState.QUEUED, completed_at=None, idempotency_key="k4")
        _insert_work_item(session, state=WorkItemState.RUNNING, completed_at=None, idempotency_key="k5")

        deleted = cleanup_expired_data(
            session, usage_retention=USAGE_RETENTION, work_item_retention=WORK_ITEM_RETENTION
        )

        remaining_keys = {w.idempotency_key for w in session.query(WorkItem).all()}
    finally:
        session.close()

    assert deleted["work_items"] == 2
    assert remaining_keys == {"k3", "k4", "k5"}


def test_empty_tables_delete_nothing(session_factory):
    session = session_factory()
    try:
        deleted = cleanup_expired_data(
            session, usage_retention=USAGE_RETENTION, work_item_retention=WORK_ITEM_RETENTION
        )
    finally:
        session.close()

    assert deleted == {"ai_usage_records": 0, "rate_limit_counters": 0, "work_items": 0}
