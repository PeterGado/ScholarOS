from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol

from app.auth.entities import AuthSession, PasswordResetToken


class AuthSessionRepository(ABC):
    """Persistence port for AuthSession. Concrete (SQLAlchemy-backed) implementation is a
    later stage - this interface exists now so AuthService can be written and unit-tested
    against it today, matching how every other module's application layer depends on a
    repository interface rather than a concrete one (e.g. AgentRepository).
    """

    @abstractmethod
    def create(self, *, user_id: int, token_hash: str) -> AuthSession: ...

    @abstractmethod
    def get_by_token_hash(self, token_hash: str) -> AuthSession | None: ...

    @abstractmethod
    def end(self, session: AuthSession) -> None:
        """Persist the `open -> ended` transition (sets `ended_at`)."""
        ...

    @abstractmethod
    def touch(self, session: AuthSession) -> None:
        """Persist an updated `last_active_at`. Activity metadata only - MUST NOT affect
        whether a session is considered valid (no timeout semantics; ADR-010 Decision item 2).
        """
        ...

    @abstractmethod
    def end_all_for_user(self, user_id: int) -> None:
        """Ends every active session for a user (2026-10-06, password reset) - a successful
        reset should not leave an attacker's existing session (the whole reason the user is
        resetting) still valid. Not used by logout, which only ever ends the one calling
        session.
        """
        ...


class PasswordResetTokenRepository(ABC):
    """Persistence port for PasswordResetToken - same shape as AuthSessionRepository, since a
    reset token is structurally a short-lived, single-use credential looked up by hash, just
    like a session token.
    """

    @abstractmethod
    def create(self, *, user_id: int, token_hash: str, expires_at: datetime) -> PasswordResetToken: ...

    @abstractmethod
    def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None: ...

    @abstractmethod
    def mark_used(self, token: PasswordResetToken) -> None:
        """Persist the single-use consumption (sets `used_at`) - called the moment a reset
        actually succeeds, so the same link can never be replayed even within its validity
        window.
        """
        ...


class UserCredential(Protocol):
    """Structural shape AuthService needs from a user record - deliberately not a direct
    dependency on `app.database.shared_models.User`, so the Authentication Boundary doesn't
    couple to that model's exact fields beyond what login actually needs.
    """

    user_id: int
    username: str
    password_hash: str
    email: str | None


class UserCredentialLookup(Protocol):
    def get_by_username(self, username: str) -> UserCredential | None: ...

    def get_by_google_subject(self, google_subject: str) -> UserCredential | None: ...

    def get_by_email(self, email: str) -> UserCredential | None: ...

    def get_by_id(self, user_id: int) -> UserCredential | None:
        """Reverse lookup from an already-verified session's user_id (GET /auth/profile) -
        every other method here looks up an unverified caller-supplied credential; this one
        never takes untrusted input, only an id that came from AuthService.verify_token.
        """
        ...


class UserRegistrationRepository(Protocol):
    """A separate, narrow write capability (ADR-011) - deliberately not added to
    UserCredentialLookup, which SqlAlchemyUserCredentialLookup's own docstring documents as
    read-only by design. Mirrors the WorkItemEnqueuer/WorkItemOutcomeLookup precedent
    (app.workers.ports) of splitting read and write capabilities into separate narrow ports
    rather than growing one interface to cover both.
    """

    def create(self, *, username: str, password_hash: str) -> UserCredential: ...

    def create_from_google(
        self, *, username: str, email: str | None, google_subject: str, display_name: str | None
    ) -> UserCredential:
        """Google Sign-In (2026-09-20): a separate method from `create()`, not an overload of
        it - a Google-only account has no password to hash, and this port's own rationale above
        is exactly "separate narrow ports rather than growing one interface to cover both."
        """
        ...


class UserAccountRepository(Protocol):
    """A third narrow write capability (2026-10-06, password reset + optional email), same
    rationale as UserRegistrationRepository's own docstring: a separate port rather than
    growing UserCredentialLookup (read-only) or UserRegistrationRepository (account creation
    only, not post-creation mutation).
    """

    def update_password_hash(self, user_id: int, password_hash: str) -> None: ...

    def update_email(self, user_id: int, email: str | None) -> None: ...
