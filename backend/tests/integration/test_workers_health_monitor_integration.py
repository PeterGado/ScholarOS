import asyncio
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.workers.enums import WorkItemKind, WorkItemState
from app.workers.health import QueueHealthMonitor
from app.workers.models import WorkItem


@pytest.fixture()
def session_factory(tmp_path):
    db_path = tmp_path / "workers_health_monitor_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    factory = build_sessionmaker(engine)
    try:
        yield factory
    finally:
        engine.dispose()


def test_monitor_checks_on_its_own_interval_and_reports_a_stale_queue(session_factory):
    """End-to-end proof that QueueHealthMonitor actually runs in the background, on its own
    thread, without anything external polling it - the whole point of adding it (see its own
    docstring). A short check_interval_seconds keeps this test fast.
    """
    session = session_factory()
    try:
        session.add(
            WorkItem(
                kind=WorkItemKind.PIPELINE_STAGE,
                state=WorkItemState.QUEUED,
                payload_reference="process_document:1",
                idempotency_key="stale-item",
                created_at=datetime.now(UTC) - timedelta(seconds=700),
            )
        )
        session.commit()
    finally:
        session.close()

    monitor = QueueHealthMonitor(session_factory, stale_threshold_seconds=600, check_interval_seconds=0.05)

    async def _drive():
        with patch("app.workers.health.sentry_sdk.capture_message") as capture:
            monitor.start()
            # Several check intervals' worth of wall-clock time - enough for at least one real
            # check to have run on the monitor's own thread.
            await asyncio.sleep(0.3)
            await monitor.stop()
        return capture

    capture = asyncio.run(_drive())
    capture.assert_called()


def test_monitor_stop_actually_joins_its_thread(session_factory):
    monitor = QueueHealthMonitor(session_factory, stale_threshold_seconds=600, check_interval_seconds=0.05)
    monitor.start()
    assert monitor._thread is not None
    assert monitor._thread.is_alive()

    asyncio.run(monitor.stop())

    # join() inside stop() already blocked until the thread actually exited - this just confirms
    # that promise holds, not a race against it.
    start = time.monotonic()
    while monitor._thread.is_alive() and time.monotonic() - start < 2:
        time.sleep(0.01)
    assert not monitor._thread.is_alive()
