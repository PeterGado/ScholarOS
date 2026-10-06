from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.auth.entities import AuthSession, EmailVerificationToken, PasswordResetToken
from app.auth.models import AuthSession as AuthSessionModel
from app.auth.models import EmailVerificationToken as EmailVerificationTokenModel
from app.auth.models import PasswordResetToken as PasswordResetTokenModel
from app.auth.repository import (
    AuthSessionRepository,
    EmailVerificationTokenRepository,
    PasswordResetTokenRepository,
    UserAccountRepository,
    UserCredential,
    UserCredentialLookup,
    UserRegistrationRepository,
)
from app.database.shared_models import User


def _as_utc(value: datetime | None) -> datetime | None:
    """PasswordResetTokenModel's datetime columns are plain `DateTime` (no `timezone=True`),
    which both SQLite and Postgres (TIMESTAMP WITHOUT TIME ZONE, the default) store and return
    naive, regardless of how they were written - a real bug this surfaced via a genuine e2e
    test, not a hypothetical: PasswordResetToken.is_valid() compares `expires_at` against
    `datetime.now(timezone.utc)`, and Python refuses to compare a naive and an aware datetime
    at all (TypeError), not silently getting the wrong answer. Every datetime this module
    persists is always UTC by convention (`datetime.now(timezone.utc)` at every write site) -
    this re-attaches that known timezone on read rather than leaving the caller to guess.
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class SqlAlchemyAuthSessionRepository(AuthSessionRepository):
    """Concrete AuthSessionRepository (app.auth.repository). Owns every SQLAlchemy detail for
    AuthSession persistence - AuthService never imports this module or SQLAlchemy directly.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, user_id: int, token_hash: str) -> AuthSession:
        row = AuthSessionModel(user_id=user_id, token_hash=token_hash)
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        row = self._session.query(AuthSessionModel).filter_by(token_hash=token_hash).one_or_none()
        return self._to_domain(row) if row is not None else None

    def end(self, session: AuthSession) -> None:
        row = self._session.get(AuthSessionModel, session.session_id)
        row.ended_at = datetime.now(timezone.utc)
        self._session.flush()
        session.ended_at = row.ended_at

    def touch(self, session: AuthSession) -> None:
        row = self._session.get(AuthSessionModel, session.session_id)
        row.last_active_at = datetime.now(timezone.utc)
        self._session.flush()
        session.last_active_at = row.last_active_at

    def end_all_for_user(self, user_id: int) -> None:
        now = datetime.now(timezone.utc)
        self._session.query(AuthSessionModel).filter_by(user_id=user_id, ended_at=None).update(
            {"ended_at": now}
        )
        self._session.flush()

    @staticmethod
    def _to_domain(row: AuthSessionModel) -> AuthSession:
        return AuthSession(
            session_id=row.session_id,
            user_id=row.user_id,
            token_hash=row.token_hash,
            started_at=row.started_at,
            last_active_at=row.last_active_at,
            ended_at=row.ended_at,
        )


class SqlAlchemyUserCredentialLookup(UserCredentialLookup):
    """Concrete UserCredentialLookup (app.auth.repository), reading the existing `users`
    table. Read-only - no registration, no account creation, nothing beyond looking up the
    one pre-provisioned account by username (ADR-010).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> UserCredential | None:
        # User structurally satisfies UserCredential (user_id, username, password_hash) -
        # returned directly, no separate DTO needed.
        return self._session.query(User).filter_by(username=username).one_or_none()

    def get_by_google_subject(self, google_subject: str) -> UserCredential | None:
        return self._session.query(User).filter_by(google_subject=google_subject).one_or_none()

    def get_by_email(self, email: str) -> UserCredential | None:
        return self._session.query(User).filter_by(email=email).one_or_none()

    def get_by_id(self, user_id: int) -> UserCredential | None:
        return self._session.get(User, user_id)


class SqlAlchemyUserRegistrationRepository(UserRegistrationRepository):
    """Concrete UserRegistrationRepository (app.auth.repository, ADR-011) - the write
    counterpart SqlAlchemyUserCredentialLookup's own docstring explicitly excludes. Separate
    class, not an addition to that one, so its "read-only" documentation stays true.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, *, username: str, password_hash: str, email: str | None = None, email_verified: bool = True
    ) -> UserCredential:
        row = User(username=username, password_hash=password_hash, email=email, email_verified=email_verified)
        self._session.add(row)
        self._session.flush()
        return row

    def create_from_google(
        self,
        *,
        username: str,
        email: str | None,
        google_subject: str,
        display_name: str | None,
        email_verified: bool = True,
    ) -> UserCredential:
        row = User(
            username=username,
            email=email,
            google_subject=google_subject,
            display_name=display_name,
            email_verified=email_verified,
        )
        self._session.add(row)
        self._session.flush()
        return row


class SqlAlchemyUserAccountRepository(UserAccountRepository):
    """Concrete UserAccountRepository (app.auth.repository, 2026-10-06) - the post-creation
    mutation counterpart neither SqlAlchemyUserCredentialLookup (read-only) nor
    SqlAlchemyUserRegistrationRepository (creation-only) cover.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def update_password_hash(self, user_id: int, password_hash: str) -> None:
        row = self._session.get(User, user_id)
        row.password_hash = password_hash
        self._session.flush()

    def update_email(self, user_id: int, email: str | None) -> None:
        row = self._session.get(User, user_id)
        row.email = email
        self._session.flush()

    def mark_email_verified(self, user_id: int) -> None:
        row = self._session.get(User, user_id)
        row.email_verified = True
        self._session.flush()

    def set_google_subject(self, user_id: int, google_subject: str) -> None:
        row = self._session.get(User, user_id)
        row.google_subject = google_subject
        self._session.flush()


class SqlAlchemyPasswordResetTokenRepository(PasswordResetTokenRepository):
    """Concrete PasswordResetTokenRepository (app.auth.repository, 2026-10-06)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, user_id: int, token_hash: str, expires_at: datetime) -> PasswordResetToken:
        row = PasswordResetTokenModel(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        row = self._session.query(PasswordResetTokenModel).filter_by(token_hash=token_hash).one_or_none()
        return self._to_domain(row) if row is not None else None

    def mark_used(self, token: PasswordResetToken) -> None:
        row = self._session.get(PasswordResetTokenModel, token.token_id)
        row.used_at = datetime.now(timezone.utc)
        self._session.flush()
        token.used_at = row.used_at

    @staticmethod
    def _to_domain(row: PasswordResetTokenModel) -> PasswordResetToken:
        return PasswordResetToken(
            token_id=row.token_id,
            user_id=row.user_id,
            token_hash=row.token_hash,
            created_at=_as_utc(row.created_at),
            expires_at=_as_utc(row.expires_at),
            used_at=_as_utc(row.used_at),
        )


class SqlAlchemyEmailVerificationTokenRepository(EmailVerificationTokenRepository):
    """Concrete EmailVerificationTokenRepository (app.auth.repository, 2026-10-06) - same shape
    as SqlAlchemyPasswordResetTokenRepository.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, user_id: int, token_hash: str, expires_at: datetime) -> EmailVerificationToken:
        row = EmailVerificationTokenModel(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get_by_token_hash(self, token_hash: str) -> EmailVerificationToken | None:
        row = self._session.query(EmailVerificationTokenModel).filter_by(token_hash=token_hash).one_or_none()
        return self._to_domain(row) if row is not None else None

    def mark_used(self, token: EmailVerificationToken) -> None:
        row = self._session.get(EmailVerificationTokenModel, token.token_id)
        row.used_at = datetime.now(timezone.utc)
        self._session.flush()
        token.used_at = row.used_at

    @staticmethod
    def _to_domain(row: EmailVerificationTokenModel) -> EmailVerificationToken:
        return EmailVerificationToken(
            token_id=row.token_id,
            user_id=row.user_id,
            token_hash=row.token_hash,
            created_at=_as_utc(row.created_at),
            expires_at=_as_utc(row.expires_at),
            used_at=_as_utc(row.used_at),
        )
