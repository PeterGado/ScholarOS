import logging

from sqlalchemy.exc import OperationalError

from app.auth.entities import AuthSession
from app.auth.exceptions import InvalidCredentialsError, InvalidSessionError
from app.auth.hashing import verify_password
from app.auth.identity import AuthenticatedIdentity
from app.auth.repository import AuthSessionRepository, UserCredentialLookup
from app.auth.tokens import generate_session_token, hash_session_token
from app.core.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class AuthService:
    """The Authentication Boundary's orchestration layer (ADR-010). Login, logout, and token
    verification live here and only here - no route, use case, or domain object touches a
    password, token, or session directly.

    Takes a UnitOfWork for the same reason CreateAgentWorkspaceUseCase does: each HTTP
    request gets its own Session from get_db(), and closing it without an explicit commit
    silently discards uncommitted writes (SQLAlchemy's default rollback-on-close). Repository
    methods only flush (visible within one transaction, e.g. shared test sessions); commit is
    this service's responsibility, exactly like every other use case in this codebase.
    """

    def __init__(
        self,
        session_repository: AuthSessionRepository,
        user_lookup: UserCredentialLookup,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._sessions = session_repository
        self._users = user_lookup
        self._uow = unit_of_work

    def login(self, *, username: str, password: str) -> str:
        """Verify credentials and create a session. Returns the raw token - the only moment
        it exists in plaintext; only its hash is ever persisted (tokens.py).
        """
        user = self._users.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        return self._create_session(user.user_id)

    def create_session_for_verified_identity(self, *, user_id: int) -> str:
        """Issue a session for an identity already verified by another means (Google Sign-In,
        2026-09-20: the ID token's signature is the verification, not a password) - skips
        credential checking entirely, unlike login(). Never call this with a user_id that
        hasn't actually been verified by the caller.
        """
        return self._create_session(user_id)

    def _create_session(self, user_id: int) -> str:
        raw_token = generate_session_token()
        try:
            self._sessions.create(user_id=user_id, token_hash=hash_session_token(raw_token))
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
        return raw_token

    def logout(self, raw_token: str) -> None:
        session = self._require_active_session(raw_token)
        try:
            self._sessions.end(session)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

    def verify_token(self, raw_token: str) -> AuthenticatedIdentity:
        session = self._require_active_session(raw_token)
        try:
            self._sessions.touch(session)
            self._uow.commit()
        except OperationalError:
            # `last_active_at` is activity metadata only (AuthSessionRepository.touch's own
            # docstring: "MUST NOT affect whether a session is considered valid") - it was
            # already documented as non-critical, but the *failure handling* here didn't match
            # that until now: every authenticated request commits this write, so two requests
            # arriving genuinely concurrently (the frontend routinely fires several in parallel,
            # e.g. DraftDetailPage's two simultaneous queries) can race for SQLite's single
            # writer slot. A transient lock on this best-effort write must not fail the whole
            # authenticated request - found via the Frontend milestone's real manual workflow.
            logger.warning("Failed to update session activity timestamp (non-critical); continuing.")
            self._uow.rollback()
        except Exception:
            self._uow.rollback()
            raise
        return AuthenticatedIdentity(user_id=session.user_id)

    def _require_active_session(self, raw_token: str) -> AuthSession:
        session = self._sessions.get_by_token_hash(hash_session_token(raw_token))
        if session is None or not session.is_active:
            raise InvalidSessionError()
        return session
