from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.entities import AuthSession
from app.auth.exceptions import InvalidInviteCodeError, UsernameAlreadyTakenError, WeakPasswordError
from app.auth.hashing import hash_password, verify_password
from app.auth.registration import MINIMUM_PASSWORD_LENGTH, RegisterUserUseCase
from app.auth.repository import AuthSessionRepository, UserCredentialLookup, UserRegistrationRepository
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


class FakeUserRegistrationRepository(UserRegistrationRepository):
    def __init__(self, lookup: FakeUserCredentialLookup, *, raise_integrity_error: bool = False) -> None:
        self._lookup = lookup
        self._next_id = max([u.user_id for u in lookup._by_username.values()], default=0) + 1
        self._raise_integrity_error = raise_integrity_error
        self.created: list[FakeUserCredential] = []

    def create(self, *, username: str, password_hash: str) -> FakeUserCredential:
        if self._raise_integrity_error:
            raise IntegrityError("INSERT INTO users", (), Exception("UNIQUE constraint failed: users.username"))
        user = FakeUserCredential(user_id=self._next_id, username=username, password_hash=password_hash)
        self._next_id += 1
        self._lookup._by_username[username] = user
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


def _build_use_case(*, existing_users=(), required_invite_code=None, raise_integrity_error=False):
    lookup = FakeUserCredentialLookup(*existing_users)
    registration = FakeUserRegistrationRepository(lookup, raise_integrity_error=raise_integrity_error)
    auth_service = AuthService(FakeAuthSessionRepository(), lookup, FakeUnitOfWork())
    use_case = RegisterUserUseCase(
        lookup, registration, auth_service, FakeUnitOfWork(), required_invite_code=required_invite_code
    )
    return use_case, lookup, registration


def test_registering_a_new_user_returns_a_usable_session_token():
    use_case, lookup, _ = _build_use_case()

    token = use_case.execute(username="new-researcher", password="a-real-password", invite_code=None)

    assert isinstance(token, str) and token
    created = lookup.get_by_username("new-researcher")
    assert created is not None
    assert verify_password("a-real-password", created.password_hash)


def test_registering_an_already_taken_username_is_rejected():
    existing = FakeUserCredential(user_id=1, username="taken", password_hash=hash_password("whatever12"))
    use_case, _, _ = _build_use_case(existing_users=[existing])

    with pytest.raises(UsernameAlreadyTakenError):
        use_case.execute(username="taken", password="a-real-password", invite_code=None)


def test_a_password_shorter_than_the_minimum_is_rejected():
    use_case, lookup, _ = _build_use_case()

    with pytest.raises(WeakPasswordError):
        use_case.execute(username="new-researcher", password="short", invite_code=None)

    assert lookup.get_by_username("new-researcher") is None  # nothing was created


def test_a_password_at_exactly_the_minimum_length_succeeds():
    use_case, _, _ = _build_use_case()

    token = use_case.execute(username="new-researcher", password="a" * MINIMUM_PASSWORD_LENGTH, invite_code=None)

    assert isinstance(token, str) and token


def test_registration_with_no_invite_code_configured_ignores_a_supplied_code():
    use_case, lookup, _ = _build_use_case(required_invite_code=None)

    use_case.execute(username="new-researcher", password="a-real-password", invite_code="anything-at-all")

    assert lookup.get_by_username("new-researcher") is not None


def test_registration_with_no_invite_code_configured_works_with_none_supplied():
    use_case, lookup, _ = _build_use_case(required_invite_code=None)

    use_case.execute(username="new-researcher", password="a-real-password", invite_code=None)

    assert lookup.get_by_username("new-researcher") is not None


def test_registration_with_a_configured_invite_code_requires_a_matching_one():
    use_case, lookup, _ = _build_use_case(required_invite_code="friends-2026")

    with pytest.raises(InvalidInviteCodeError):
        use_case.execute(username="new-researcher", password="a-real-password", invite_code="wrong-code")
    with pytest.raises(InvalidInviteCodeError):
        use_case.execute(username="new-researcher", password="a-real-password", invite_code=None)

    assert lookup.get_by_username("new-researcher") is None  # neither attempt created anything


def test_registration_with_the_correct_invite_code_succeeds():
    use_case, lookup, _ = _build_use_case(required_invite_code="friends-2026")

    use_case.execute(username="new-researcher", password="a-real-password", invite_code="friends-2026")

    assert lookup.get_by_username("new-researcher") is not None


def test_a_race_on_username_uniqueness_is_translated_to_the_same_domain_error():
    """The get_by_username check and the create() insert are two separate statements - a
    second registration for the same username arriving in that narrow window hits the real
    UNIQUE constraint instead. Must surface as the same UsernameAlreadyTakenError, not a raw
    IntegrityError.
    """
    use_case, _, _ = _build_use_case(raise_integrity_error=True)

    with pytest.raises(UsernameAlreadyTakenError):
        use_case.execute(username="new-researcher", password="a-real-password", invite_code=None)
