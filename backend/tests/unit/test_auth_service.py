from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.auth.entities import AuthSession
from app.auth.exceptions import InvalidCredentialsError, InvalidSessionError
from app.auth.hashing import hash_password
from app.auth.repository import AuthSessionRepository, UserCredentialLookup
from app.auth.service import AuthService


@dataclass
class FakeUserCredential:
    user_id: int
    username: str
    password_hash: str


class FakeUserCredentialLookup(UserCredentialLookup):
    def __init__(self, *users: FakeUserCredential):
        self._by_username = {u.username: u for u in users}

    def get_by_username(self, username: str) -> FakeUserCredential | None:
        return self._by_username.get(username)


class FakeAuthSessionRepository(AuthSessionRepository):
    def __init__(self):
        self._by_hash: dict[str, AuthSession] = {}
        self._next_id = 1
        self.touch_calls = 0

    def create(self, *, user_id: int, token_hash: str) -> AuthSession:
        session = AuthSession(
            session_id=self._next_id,
            user_id=user_id,
            token_hash=token_hash,
            started_at=datetime.now(timezone.utc),
        )
        self._next_id += 1
        self._by_hash[token_hash] = session
        return session

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        return self._by_hash.get(token_hash)

    def end(self, session: AuthSession) -> None:
        session.ended_at = datetime.now(timezone.utc)

    def touch(self, session: AuthSession) -> None:
        self.touch_calls += 1
        session.last_active_at = datetime.now(timezone.utc)


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _build_service(*users: FakeUserCredential):
    sessions = FakeAuthSessionRepository()
    users_repo = FakeUserCredentialLookup(*users)
    return AuthService(sessions, users_repo, FakeUnitOfWork()), sessions


def test_login_with_correct_credentials_returns_a_token_and_creates_a_session():
    user = FakeUserCredential(user_id=7, username="researcher", password_hash=hash_password("s3cret"))
    service, sessions = _build_service(user)

    token = service.login(username="researcher", password="s3cret")

    assert isinstance(token, str)
    identity = service.verify_token(token)
    assert identity.user_id == 7


def test_login_commits_so_the_session_survives_the_request_that_created_it():
    """Regression guard: repositories only flush; login() itself must commit, or a session
    created in one HTTP request is silently rolled back when that request's Session closes.
    """
    user = FakeUserCredential(user_id=7, username="researcher", password_hash=hash_password("s3cret"))
    sessions = FakeAuthSessionRepository()
    uow = FakeUnitOfWork()
    service = AuthService(sessions, FakeUserCredentialLookup(user), uow)

    service.login(username="researcher", password="s3cret")

    assert uow.committed is True


def test_logout_commits_so_the_ended_session_survives_the_request():
    user = FakeUserCredential(user_id=7, username="researcher", password_hash=hash_password("s3cret"))
    sessions = FakeAuthSessionRepository()
    uow = FakeUnitOfWork()
    service = AuthService(sessions, FakeUserCredentialLookup(user), uow)
    token = service.login(username="researcher", password="s3cret")
    uow.committed = False  # reset to isolate logout's own commit

    service.logout(token)

    assert uow.committed is True


def test_login_with_unknown_username_raises_invalid_credentials():
    service, _ = _build_service()
    with pytest.raises(InvalidCredentialsError):
        service.login(username="nobody", password="whatever")


def test_login_with_wrong_password_raises_invalid_credentials():
    user = FakeUserCredential(user_id=7, username="researcher", password_hash=hash_password("s3cret"))
    service, _ = _build_service(user)

    with pytest.raises(InvalidCredentialsError):
        service.login(username="researcher", password="wrong")


def test_unknown_username_and_wrong_password_raise_the_same_error_type_and_message():
    """No username enumeration: both failure modes must be indistinguishable to the caller."""
    user = FakeUserCredential(user_id=7, username="researcher", password_hash=hash_password("s3cret"))
    service, _ = _build_service(user)

    with pytest.raises(InvalidCredentialsError) as unknown_user_exc:
        service.login(username="nobody", password="whatever")
    with pytest.raises(InvalidCredentialsError) as wrong_password_exc:
        service.login(username="researcher", password="wrong")

    assert str(unknown_user_exc.value) == str(wrong_password_exc.value)


def test_verify_token_rejects_an_unknown_token():
    service, _ = _build_service()
    with pytest.raises(InvalidSessionError):
        service.verify_token("not-a-real-token")


def test_logout_ends_the_session_and_it_can_no_longer_be_verified():
    user = FakeUserCredential(user_id=7, username="researcher", password_hash=hash_password("s3cret"))
    service, _ = _build_service(user)
    token = service.login(username="researcher", password="s3cret")

    service.logout(token)

    with pytest.raises(InvalidSessionError):
        service.verify_token(token)


def test_logout_with_an_invalid_token_raises_invalid_session():
    service, _ = _build_service()
    with pytest.raises(InvalidSessionError):
        service.logout("not-a-real-token")


def test_verify_token_touches_the_session_for_activity_metadata():
    user = FakeUserCredential(user_id=7, username="researcher", password_hash=hash_password("s3cret"))
    service, sessions = _build_service(user)
    token = service.login(username="researcher", password="s3cret")

    service.verify_token(token)

    assert sessions.touch_calls == 1


def test_a_session_with_a_very_stale_last_active_at_is_still_valid():
    """Regression guard for ADR-010 Decision item 2 at the service layer: no automatic
    expiry, no idle timeout - only explicit logout ends a session.
    """
    user = FakeUserCredential(user_id=7, username="researcher", password_hash=hash_password("s3cret"))
    service, sessions = _build_service(user)
    token = service.login(username="researcher", password="s3cret")

    stored_session = next(iter(sessions._by_hash.values()))
    stored_session.last_active_at = datetime.now(timezone.utc) - timedelta(days=365)
    stored_session.started_at = datetime.now(timezone.utc) - timedelta(days=365)

    identity = service.verify_token(token)
    assert identity.user_id == 7
