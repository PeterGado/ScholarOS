from abc import ABC, abstractmethod
from typing import Protocol

from app.auth.entities import AuthSession


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


class UserCredential(Protocol):
    """Structural shape AuthService needs from a user record - deliberately not a direct
    dependency on `app.database.shared_models.User`, so the Authentication Boundary doesn't
    couple to that model's exact fields beyond what login actually needs.
    """

    user_id: int
    username: str
    password_hash: str


class UserCredentialLookup(Protocol):
    def get_by_username(self, username: str) -> UserCredential | None: ...
