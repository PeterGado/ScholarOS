from datetime import datetime, timedelta, timezone

from app.auth.entities import AuthSession


def test_a_fresh_session_is_active():
    session = AuthSession(user_id=1, token_hash="hash", started_at=datetime.now(timezone.utc))
    assert session.is_active is True


def test_an_ended_session_is_not_active():
    session = AuthSession(
        user_id=1,
        token_hash="hash",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )
    assert session.is_active is False


def test_a_very_old_last_active_at_does_not_make_a_session_inactive():
    """Regression guard for ADR-010 Decision item 2: there is no automatic, time-based
    expiry in this milestone. A session with a stale last_active_at is still valid - only
    ended_at determines validity.
    """
    long_ago = datetime.now(timezone.utc) - timedelta(days=365)
    session = AuthSession(
        user_id=1,
        token_hash="hash",
        started_at=long_ago,
        last_active_at=long_ago,
    )
    assert session.is_active is True
