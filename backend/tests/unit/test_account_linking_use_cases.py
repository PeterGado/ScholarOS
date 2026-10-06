from dataclasses import dataclass

import pytest

from app.auth.account_linking import ConnectGoogleAccountUseCase, SetPasswordUseCase
from app.auth.exceptions import (
    GoogleAccountAlreadyLinkedError,
    GoogleSignInNotConfiguredError,
    InvalidGoogleTokenError,
    PasswordCompromisedError,
    WeakPasswordError,
)
from app.auth.hashing import verify_password
from app.auth.repository import UserAccountRepository, UserCredentialLookup

GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"


@dataclass
class FakeUserCredential:
    user_id: int
    username: str
    password_hash: str = ""
    email: str | None = None
    google_subject: str | None = None
    email_verified: bool = True


class FakeUserCredentialLookup(UserCredentialLookup):
    def __init__(self, *users: FakeUserCredential):
        self._users = list(users)

    def get_by_username(self, username):
        raise NotImplementedError

    def get_by_google_subject(self, google_subject):
        return next((u for u in self._users if u.google_subject == google_subject), None)

    def get_by_email(self, email):
        raise NotImplementedError

    def get_by_id(self, user_id):
        return next((u for u in self._users if u.user_id == user_id), None)


class FakeUserAccountRepository(UserAccountRepository):
    def __init__(self):
        self.google_subjects: dict[int, str] = {}
        self.verified: set[int] = set()
        self.password_hashes: dict[int, str] = {}

    def update_password_hash(self, user_id, password_hash):
        self.password_hashes[user_id] = password_hash

    def update_email(self, user_id, email):
        raise NotImplementedError

    def mark_email_verified(self, user_id):
        self.verified.add(user_id)

    def set_google_subject(self, user_id, google_subject):
        self.google_subjects[user_id] = google_subject


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
        return claims or {"sub": "google-subject-1", "email": "alice@example.com", "email_verified": True}

    return verify


# --- ConnectGoogleAccountUseCase -------------------------------------------------------------


def _build_connect_use_case(*, existing_users=(), google_client_id=GOOGLE_CLIENT_ID, verifier=None):
    lookup = FakeUserCredentialLookup(*existing_users)
    user_account = FakeUserAccountRepository()
    uow = FakeUnitOfWork()
    use_case = ConnectGoogleAccountUseCase(
        lookup, user_account, uow, verifier or _verifier(), google_client_id=google_client_id
    )
    return use_case, user_account, uow


def test_connecting_a_fresh_google_identity_links_it_to_the_current_account():
    use_case, user_account, uow = _build_connect_use_case()

    use_case.execute(user_id=7, id_token="raw-token")

    assert user_account.google_subjects[7] == "google-subject-1"
    assert 7 in user_account.verified
    assert uow.committed is True


def test_connecting_does_not_mark_verified_when_googles_claim_does_not_confirm_it():
    use_case, user_account, _ = _build_connect_use_case(
        verifier=_verifier({"sub": "google-subject-1", "email": "alice@example.com", "email_verified": False})
    )

    use_case.execute(user_id=7, id_token="raw-token")

    assert user_account.google_subjects[7] == "google-subject-1"
    assert 7 not in user_account.verified


def test_connecting_a_google_identity_already_linked_to_a_different_account_is_rejected():
    other_account = FakeUserCredential(user_id=99, username="bob", google_subject="google-subject-1")
    use_case, user_account, uow = _build_connect_use_case(existing_users=[other_account])

    with pytest.raises(GoogleAccountAlreadyLinkedError):
        use_case.execute(user_id=7, id_token="raw-token")

    assert 7 not in user_account.google_subjects
    assert uow.committed is False


def test_connecting_a_google_identity_already_linked_to_the_same_account_is_a_no_op_success():
    """Re-connecting an already-linked Google account (e.g. a double click) must not be treated
    as a conflict against itself."""
    own_account = FakeUserCredential(user_id=7, username="alice", google_subject="google-subject-1")
    use_case, user_account, _ = _build_connect_use_case(existing_users=[own_account])

    use_case.execute(user_id=7, id_token="raw-token")

    assert user_account.google_subjects[7] == "google-subject-1"


def test_an_invalid_google_token_is_rejected():
    use_case, user_account, uow = _build_connect_use_case(verifier=_verifier(error=True))

    with pytest.raises(InvalidGoogleTokenError):
        use_case.execute(user_id=7, id_token="garbage")

    assert uow.committed is False


def test_connecting_when_google_sign_in_is_not_configured_is_rejected():
    use_case, _, _ = _build_connect_use_case(google_client_id=None)

    with pytest.raises(GoogleSignInNotConfiguredError):
        use_case.execute(user_id=7, id_token="raw-token")


# --- SetPasswordUseCase -----------------------------------------------------------------------


def _build_set_password_use_case(*, is_breached=lambda password: False):
    user_account = FakeUserAccountRepository()
    uow = FakeUnitOfWork()
    use_case = SetPasswordUseCase(user_account, uow, is_breached=is_breached)
    return use_case, user_account, uow


def test_setting_a_password_hashes_and_stores_it():
    use_case, user_account, uow = _build_set_password_use_case()

    use_case.execute(user_id=7, password="a-real-password")

    assert verify_password("a-real-password", user_account.password_hashes[7])
    assert uow.committed is True


def test_a_password_shorter_than_the_minimum_is_rejected():
    use_case, user_account, _ = _build_set_password_use_case()

    with pytest.raises(WeakPasswordError):
        use_case.execute(user_id=7, password="short")

    assert 7 not in user_account.password_hashes


def test_a_breached_password_is_rejected():
    use_case, user_account, _ = _build_set_password_use_case(is_breached=lambda password: True)

    with pytest.raises(PasswordCompromisedError):
        use_case.execute(user_id=7, password="a-real-password")

    assert 7 not in user_account.password_hashes
