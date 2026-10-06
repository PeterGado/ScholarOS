from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.auth.entities import AuthSession, PasswordResetToken
from app.auth.exceptions import InvalidResetTokenError, PasswordCompromisedError, WeakPasswordError
from app.auth.hashing import hash_password, verify_password
from app.auth.password_reset import ConfirmPasswordResetUseCase, RequestPasswordResetUseCase
from app.auth.repository import AuthSessionRepository, PasswordResetTokenRepository, UserAccountRepository, UserCredentialLookup
from app.auth.tokens import hash_session_token
from app.email.exceptions import EmailSendError


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


class FakePasswordResetTokenRepository(PasswordResetTokenRepository):
    def __init__(self):
        self._by_hash: dict[str, PasswordResetToken] = {}
        self._next_id = 1

    def create(self, *, user_id, token_hash, expires_at):
        token = PasswordResetToken(
            token_id=self._next_id, user_id=user_id, token_hash=token_hash,
            created_at=datetime.now(timezone.utc), expires_at=expires_at,
        )
        self._next_id += 1
        self._by_hash[token_hash] = token
        return token

    def get_by_token_hash(self, token_hash):
        return self._by_hash.get(token_hash)

    def mark_used(self, token):
        token.used_at = datetime.now(timezone.utc)


class FakeUserAccountRepository(UserAccountRepository):
    def __init__(self):
        self.password_hashes: dict[int, str] = {}

    def update_password_hash(self, user_id, password_hash):
        self.password_hashes[user_id] = password_hash

    def update_email(self, user_id, email):
        raise NotImplementedError


class FakeAuthSessionRepository(AuthSessionRepository):
    def __init__(self):
        self.ended_all_for_user: list[int] = []

    def create(self, *, user_id, token_hash):
        raise NotImplementedError

    def get_by_token_hash(self, token_hash):
        raise NotImplementedError

    def end(self, session):
        raise NotImplementedError

    def touch(self, session):
        raise NotImplementedError

    def end_all_for_user(self, user_id):
        self.ended_all_for_user.append(user_id)


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


# --- RequestPasswordResetUseCase -------------------------------------------------------------


def _build_request_use_case(*users, email_sender=None):
    sent = []

    def default_sender(**kwargs):
        sent.append(kwargs)

    reset_tokens = FakePasswordResetTokenRepository()
    use_case = RequestPasswordResetUseCase(
        FakeUserCredentialLookup(*users),
        reset_tokens,
        FakeUnitOfWork(),
        token_ttl_minutes=60,
        frontend_base_url="http://localhost:5173",
        resend_api_key="re_test",
        from_address="ScholarOS <onboarding@resend.dev>",
        email_sender=email_sender or default_sender,
    )
    return use_case, reset_tokens, sent


def test_a_matching_email_creates_a_token_and_sends_an_email():
    user = FakeUserCredential(user_id=7, username="researcher", password_hash="h", email="r@example.com")
    use_case, reset_tokens, sent = _build_request_use_case(user)

    use_case.execute(email="r@example.com")

    assert len(reset_tokens._by_hash) == 1
    assert len(sent) == 1
    assert sent[0]["to"] == "r@example.com"
    assert "reset-password?token=" in sent[0]["html"]


def test_a_nonexistent_email_creates_no_token_and_sends_no_email():
    use_case, reset_tokens, sent = _build_request_use_case()  # no users at all

    use_case.execute(email="nobody@example.com")

    assert len(reset_tokens._by_hash) == 0
    assert len(sent) == 0


def test_an_email_send_failure_is_swallowed_not_raised():
    user = FakeUserCredential(user_id=7, username="researcher", password_hash="h", email="r@example.com")

    def failing_sender(**kwargs):
        raise EmailSendError("simulated provider outage")

    use_case, reset_tokens, _sent = _build_request_use_case(user, email_sender=failing_sender)

    use_case.execute(email="r@example.com")  # must not raise

    assert len(reset_tokens._by_hash) == 1  # the token still exists despite the failed send


# --- ConfirmPasswordResetUseCase -------------------------------------------------------------


def _build_confirm_use_case(*, is_breached=lambda password: False):
    reset_tokens = FakePasswordResetTokenRepository()
    user_account = FakeUserAccountRepository()
    sessions = FakeAuthSessionRepository()
    uow = FakeUnitOfWork()
    use_case = ConfirmPasswordResetUseCase(reset_tokens, user_account, sessions, uow, is_breached=is_breached)
    return use_case, reset_tokens, user_account, sessions, uow


def test_a_valid_token_resets_the_password_and_ends_all_sessions():
    use_case, reset_tokens, user_account, sessions, uow = _build_confirm_use_case()
    token = reset_tokens.create(
        user_id=7, token_hash=hash_session_token("raw-token"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    use_case.execute(raw_token="raw-token", new_password="a-new-strong-password")

    assert verify_password("a-new-strong-password", user_account.password_hashes[7])
    assert token.used_at is not None
    assert sessions.ended_all_for_user == [7]
    assert uow.committed is True


def test_an_unknown_token_is_rejected():
    use_case, *_ = _build_confirm_use_case()

    with pytest.raises(InvalidResetTokenError):
        use_case.execute(raw_token="never-issued", new_password="a-new-strong-password")


def test_an_expired_token_is_rejected():
    use_case, reset_tokens, *_ = _build_confirm_use_case()
    reset_tokens.create(
        user_id=7, token_hash=hash_session_token("raw-token"),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    with pytest.raises(InvalidResetTokenError):
        use_case.execute(raw_token="raw-token", new_password="a-new-strong-password")


def test_an_already_used_token_cannot_be_replayed():
    use_case, reset_tokens, *_ = _build_confirm_use_case()
    token = reset_tokens.create(
        user_id=7, token_hash=hash_session_token("raw-token"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    reset_tokens.mark_used(token)

    with pytest.raises(InvalidResetTokenError):
        use_case.execute(raw_token="raw-token", new_password="a-new-strong-password")


def test_a_weak_new_password_is_rejected():
    use_case, reset_tokens, *_ = _build_confirm_use_case()
    reset_tokens.create(
        user_id=7, token_hash=hash_session_token("raw-token"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    with pytest.raises(WeakPasswordError):
        use_case.execute(raw_token="raw-token", new_password="short")


def test_a_breached_new_password_is_rejected():
    use_case, reset_tokens, *_ = _build_confirm_use_case(is_breached=lambda password: True)
    reset_tokens.create(
        user_id=7, token_hash=hash_session_token("raw-token"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    with pytest.raises(PasswordCompromisedError):
        use_case.execute(raw_token="raw-token", new_password="a-new-strong-password")
