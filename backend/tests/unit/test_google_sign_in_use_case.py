from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.entities import AuthSession
from app.auth.exceptions import (
    GoogleAccountEmailConflictError,
    GoogleSignInNotConfiguredError,
    InvalidGoogleTokenError,
    InvalidInviteCodeError,
)
from app.auth.google_sign_in import GoogleSignInUseCase
from app.auth.repository import AuthSessionRepository, UserCredentialLookup, UserRegistrationRepository
from app.auth.service import AuthService

GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"


@dataclass
class FakeUserCredential:
    user_id: int
    username: str
    password_hash: str = ""
    email: str | None = None
    google_subject: str | None = None


class FakeUserCredentialLookup(UserCredentialLookup):
    def __init__(self, *users: FakeUserCredential):
        self._users = list(users)

    def get_by_username(self, username: str) -> FakeUserCredential | None:
        return next((u for u in self._users if u.username == username), None)

    def get_by_google_subject(self, google_subject: str) -> FakeUserCredential | None:
        return next((u for u in self._users if u.google_subject == google_subject), None)

    def get_by_email(self, email: str) -> FakeUserCredential | None:
        return next((u for u in self._users if u.email == email), None)


class FakeUserRegistrationRepository(UserRegistrationRepository):
    def __init__(self, lookup: FakeUserCredentialLookup, *, raise_integrity_error: bool = False) -> None:
        self._lookup = lookup
        self._next_id = max([u.user_id for u in lookup._users], default=0) + 1
        self._raise_integrity_error = raise_integrity_error
        self.created: list[FakeUserCredential] = []

    def create(self, *, username: str, password_hash: str) -> FakeUserCredential:
        raise NotImplementedError("not exercised by these tests")

    def create_from_google(
        self, *, username: str, email: str | None, google_subject: str, display_name: str | None
    ) -> FakeUserCredential:
        if self._raise_integrity_error:
            raise IntegrityError("INSERT INTO users", (), Exception("UNIQUE constraint failed"))
        user = FakeUserCredential(user_id=self._next_id, username=username, email=email, google_subject=google_subject)
        self._next_id += 1
        self._lookup._users.append(user)
        self.created.append(user)
        return user


class FakeAuthSessionRepository(AuthSessionRepository):
    def __init__(self):
        self._by_hash: dict[str, AuthSession] = {}
        self._next_id = 1

    def create(self, *, user_id: int, token_hash: str) -> AuthSession:
        session = AuthSession(session_id=self._next_id, user_id=user_id, token_hash=token_hash, started_at=datetime.now(timezone.utc))
        self._next_id += 1
        self._by_hash[token_hash] = session
        return session

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        return self._by_hash.get(token_hash)

    def end(self, session: AuthSession) -> None:
        session.ended_at = datetime.now(timezone.utc)

    def touch(self, session: AuthSession) -> None:
        session.last_active_at = datetime.now(timezone.utc)


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _verifier(claims: dict | None = None, *, error: bool = False):
    def verify(id_token: str, *, client_id: str):
        if error:
            raise ValueError("invalid token")
        assert client_id == GOOGLE_CLIENT_ID
        return claims or {"sub": "google-subject-1", "email": "alice@example.com", "email_verified": True, "name": "Alice"}

    return verify


def _build_use_case(
    *,
    existing_users=(),
    required_invite_code=None,
    google_client_id=GOOGLE_CLIENT_ID,
    verifier=None,
    raise_integrity_error=False,
):
    lookup = FakeUserCredentialLookup(*existing_users)
    registration = FakeUserRegistrationRepository(lookup, raise_integrity_error=raise_integrity_error)
    auth_service = AuthService(FakeAuthSessionRepository(), lookup, FakeUnitOfWork())
    use_case = GoogleSignInUseCase(
        lookup,
        registration,
        auth_service,
        FakeUnitOfWork(),
        verifier or _verifier(),
        required_invite_code=required_invite_code,
        google_client_id=google_client_id,
    )
    return use_case, lookup, registration


def test_a_brand_new_google_user_with_no_invite_required_gets_a_usable_token():
    use_case, lookup, _ = _build_use_case()

    token = use_case.execute(id_token="raw-token", invite_code=None)

    assert isinstance(token, str) and token
    created = lookup.get_by_google_subject("google-subject-1")
    assert created is not None
    assert created.email == "alice@example.com"
    assert created.username == "alice"


def test_username_is_derived_from_the_email_local_part():
    use_case, lookup, _ = _build_use_case()

    use_case.execute(id_token="raw-token", invite_code=None)

    assert lookup.get_by_username("alice") is not None


def test_a_username_collision_gets_a_numeric_suffix():
    existing = FakeUserCredential(user_id=1, username="alice", password_hash="hashed")
    use_case, lookup, _ = _build_use_case(existing_users=[existing])

    use_case.execute(id_token="raw-token", invite_code=None)

    assert lookup.get_by_username("alice2") is not None


def test_falls_back_to_the_google_subject_when_there_is_no_email():
    use_case, lookup, _ = _build_use_case(verifier=_verifier({"sub": "google-subject-2"}))

    use_case.execute(id_token="raw-token", invite_code=None)

    created = lookup.get_by_google_subject("google-subject-2")
    assert created is not None
    assert created.username == "google-subject-2"
    assert created.email is None


def test_a_returning_google_user_is_logged_in_without_creating_a_second_account():
    existing = FakeUserCredential(user_id=7, username="alice", email="alice@example.com", google_subject="google-subject-1")
    use_case, lookup, registration = _build_use_case(existing_users=[existing])

    token = use_case.execute(id_token="raw-token", invite_code=None)

    assert isinstance(token, str) and token
    assert registration.created == []  # no new account was created


def test_a_returning_google_user_is_not_asked_for_an_invite_code_even_when_one_is_configured():
    existing = FakeUserCredential(user_id=7, username="alice", email="alice@example.com", google_subject="google-subject-1")
    use_case, _, _ = _build_use_case(existing_users=[existing], required_invite_code="friends-2026")

    token = use_case.execute(id_token="raw-token", invite_code=None)

    assert isinstance(token, str) and token


def test_a_brand_new_user_with_the_correct_invite_code_succeeds():
    use_case, lookup, _ = _build_use_case(required_invite_code="friends-2026")

    use_case.execute(id_token="raw-token", invite_code="friends-2026")

    assert lookup.get_by_google_subject("google-subject-1") is not None


def test_a_brand_new_user_with_the_wrong_invite_code_is_rejected():
    use_case, lookup, _ = _build_use_case(required_invite_code="friends-2026")

    with pytest.raises(InvalidInviteCodeError):
        use_case.execute(id_token="raw-token", invite_code="wrong-code")

    assert lookup.get_by_google_subject("google-subject-1") is None


def test_a_brand_new_user_with_a_missing_invite_code_is_rejected():
    use_case, lookup, _ = _build_use_case(required_invite_code="friends-2026")

    with pytest.raises(InvalidInviteCodeError):
        use_case.execute(id_token="raw-token", invite_code=None)

    assert lookup.get_by_google_subject("google-subject-1") is None


def test_an_invalid_token_is_rejected():
    use_case, _, _ = _build_use_case(verifier=_verifier(error=True))

    with pytest.raises(InvalidGoogleTokenError):
        use_case.execute(id_token="garbage", invite_code=None)


def test_a_verified_email_colliding_with_an_existing_password_account_is_rejected():
    existing = FakeUserCredential(user_id=3, username="alice-password", email="alice@example.com", password_hash="hashed")
    use_case, lookup, registration = _build_use_case(existing_users=[existing])

    with pytest.raises(GoogleAccountEmailConflictError):
        use_case.execute(id_token="raw-token", invite_code=None)

    assert registration.created == []  # no account was silently linked or duplicated


def test_an_unverified_email_does_not_trigger_the_conflict_check():
    existing = FakeUserCredential(user_id=3, username="alice-password", email="alice@example.com", password_hash="hashed")
    unverified_claims = {"sub": "google-subject-1", "email": "alice@example.com", "email_verified": False, "name": "Alice"}
    use_case, lookup, _ = _build_use_case(existing_users=[existing], verifier=_verifier(unverified_claims))

    # Does not raise GoogleAccountEmailConflictError - an unverified email proves nothing.
    token = use_case.execute(id_token="raw-token", invite_code=None)

    assert isinstance(token, str) and token


def test_no_configured_client_id_is_rejected_before_verifying_anything():
    use_case, _, _ = _build_use_case(google_client_id=None)

    with pytest.raises(GoogleSignInNotConfiguredError):
        use_case.execute(id_token="raw-token", invite_code=None)


def test_a_concurrent_duplicate_registration_race_logs_in_instead_of_erroring():
    """Two concurrent first-time sign-ins for the same Google identity: the get_by_google_subject
    check passes for both, but only one insert can win the unique constraint. The loser must
    recover by logging in as the account the winner just created, not surface a raw error.
    """
    use_case, lookup, registration = _build_use_case(raise_integrity_error=True)
    # Simulate the winning request having already created the account between this request's
    # check and its own insert attempt.
    lookup._users.append(FakeUserCredential(user_id=99, username="alice", email="alice@example.com", google_subject="google-subject-1"))

    token = use_case.execute(id_token="raw-token", invite_code=None)

    assert isinstance(token, str) and token
