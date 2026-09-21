"""PostgresRateLimitStorage (2026-09-21, second infra/scaling security pass) against a real
SQLite database - it only ever issues plain SQL (a single INSERT ... ON CONFLICT DO UPDATE ...
RETURNING for incr, plain SELECT/DELETE otherwise), so a real database, not a fake, is what
actually proves the fixed-window semantics and the redeploy-survival property this backend
exists for. Mirrors tests/e2e/conftest.py's own db_engine fixture: monkeypatches
app.database.session.engine rather than passing an engine directly, since
PostgresRateLimitStorage reads app.database.session.engine fresh on every call (the same
stale-binding concern get_db()/init_db() already have to avoid).
"""

import time

import pytest

import app.database.session as db_session
from app.core.rate_limit_storage import PostgresRateLimitStorage
from app.database.session import build_engine, init_db


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    engine = build_engine(f"sqlite:///{tmp_path / 'rate_limit_test.db'}")
    init_db(engine)
    monkeypatch.setattr(db_session, "engine", engine)
    yield PostgresRateLimitStorage()
    engine.dispose()


def test_incr_starts_a_fresh_window_at_the_given_amount(storage):
    assert storage.incr("key-a", expiry=60) == 1


def test_incr_accumulates_within_the_same_window(storage):
    storage.incr("key-a", expiry=60)
    storage.incr("key-a", expiry=60)

    assert storage.incr("key-a", expiry=60) == 3


def test_incr_resets_the_counter_once_the_window_has_expired(storage):
    storage.incr("key-a", expiry=0)
    time.sleep(0.01)

    assert storage.incr("key-a", expiry=60) == 1


def test_incr_tracks_different_keys_independently(storage):
    storage.incr("key-a", expiry=60)
    storage.incr("key-a", expiry=60)
    storage.incr("key-b", expiry=60)

    assert storage.get("key-a") == 2
    assert storage.get("key-b") == 1


def test_get_returns_zero_for_an_unknown_key(storage):
    assert storage.get("never-seen") == 0


def test_get_returns_the_current_counter_value(storage):
    storage.incr("key-a", expiry=60, amount=5)

    assert storage.get("key-a") == 5


def test_get_returns_zero_once_the_window_has_expired(storage):
    storage.incr("key-a", expiry=0)
    time.sleep(0.01)

    assert storage.get("key-a") == 0


def test_get_expiry_returns_the_window_end(storage):
    before = time.time()
    storage.incr("key-a", expiry=60)
    after = time.time()

    expiry = storage.get_expiry("key-a")

    assert before + 60 <= expiry <= after + 60


def test_get_expiry_of_an_unknown_key_is_approximately_now(storage):
    before = time.time()

    expiry = storage.get_expiry("never-seen")

    assert before <= expiry <= time.time() + 0.5


def test_check_reports_a_healthy_database(storage):
    assert storage.check() is True


def test_clear_removes_only_the_given_key(storage):
    storage.incr("key-a", expiry=60)
    storage.incr("key-b", expiry=60)

    storage.clear("key-a")

    assert storage.get("key-a") == 0
    assert storage.get("key-b") == 1


def test_reset_removes_every_key(storage):
    storage.incr("key-a", expiry=60)
    storage.incr("key-b", expiry=60)

    storage.reset()

    assert storage.get("key-a") == 0
    assert storage.get("key-b") == 0


def test_a_fresh_storage_instance_sees_counts_a_prior_instance_wrote(storage):
    """The whole point of this backend over slowapi's default in-memory store: a fresh
    process (a fresh Storage instance) reusing the same underlying database still sees prior
    counts - a redeploy does not silently reset every rate limit.
    """
    storage.incr("key-a", expiry=60)
    storage.incr("key-a", expiry=60)

    fresh_storage = PostgresRateLimitStorage()

    assert fresh_storage.incr("key-a", expiry=60) == 3
