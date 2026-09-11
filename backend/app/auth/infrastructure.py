from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.auth.entities import AuthSession
from app.auth.models import AuthSession as AuthSessionModel
from app.auth.repository import AuthSessionRepository, UserCredential, UserCredentialLookup
from app.database.shared_models import User


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
