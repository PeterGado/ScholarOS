from dataclasses import dataclass

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.account import UpdateEmailUseCase
from app.auth.exceptions import EmailAlreadyInUseError
from app.auth.repository import UserAccountRepository, UserCredentialLookup


@dataclass
class FakeUserCredential:
    user_id: int
    username: str
    password_hash: str
    email: str | None = None


class FakeUserCredentialLookup(UserCredentialLookup):
    def __init__(self, *users: FakeUserCredential):
        self._by_email = {u.email: u for u in users if u.email}

    def get_by_username(self, username):
        raise NotImplementedError

    def get_by_google_subject(self, google_subject):
        raise NotImplementedError

    def get_by_email(self, email):
        return self._by_email.get(email)

    def get_by_id(self, user_id):
        raise NotImplementedError


class FakeUserAccountRepository(UserAccountRepository):
    def __init__(self, *, raise_integrity_error: bool = False):
        self.emails: dict[int, str] = {}
        self._raise_integrity_error = raise_integrity_error

    def update_password_hash(self, user_id, password_hash):
        raise NotImplementedError

    def update_email(self, user_id, email):
        if self._raise_integrity_error:
            raise IntegrityError("UPDATE users SET email=?", (), Exception("UNIQUE constraint failed"))
        self.emails[user_id] = email


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_updating_to_an_unused_email_succeeds():
    users = FakeUserCredentialLookup()
    user_account = FakeUserAccountRepository()
    uow = FakeUnitOfWork()
    use_case = UpdateEmailUseCase(users, user_account, uow)

    use_case.execute(user_id=7, email="new@example.com")

    assert user_account.emails[7] == "new@example.com"
    assert uow.committed is True


def test_updating_to_another_accounts_email_is_rejected():
    existing = FakeUserCredential(user_id=99, username="other", password_hash="h", email="taken@example.com")
    users = FakeUserCredentialLookup(existing)
    user_account = FakeUserAccountRepository()
    uow = FakeUnitOfWork()
    use_case = UpdateEmailUseCase(users, user_account, uow)

    with pytest.raises(EmailAlreadyInUseError):
        use_case.execute(user_id=7, email="taken@example.com")

    assert 7 not in user_account.emails


def test_updating_to_ones_own_current_email_is_allowed():
    existing = FakeUserCredential(user_id=7, username="researcher", password_hash="h", email="mine@example.com")
    users = FakeUserCredentialLookup(existing)
    user_account = FakeUserAccountRepository()
    uow = FakeUnitOfWork()
    use_case = UpdateEmailUseCase(users, user_account, uow)

    use_case.execute(user_id=7, email="mine@example.com")  # must not raise

    assert user_account.emails[7] == "mine@example.com"


def test_a_race_condition_at_the_database_level_is_translated_to_the_same_domain_error():
    users = FakeUserCredentialLookup()  # the check-first pass finds nothing taken
    user_account = FakeUserAccountRepository(raise_integrity_error=True)  # but the write still races
    uow = FakeUnitOfWork()
    use_case = UpdateEmailUseCase(users, user_account, uow)

    with pytest.raises(EmailAlreadyInUseError):
        use_case.execute(user_id=7, email="new@example.com")

    assert uow.rolled_back is True
