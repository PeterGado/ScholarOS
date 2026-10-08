from collections.abc import Callable

from sqlalchemy.exc import IntegrityError

from app.auth.email_verification import RequestEmailVerificationUseCase
from app.auth.exceptions import (
    EmailAlreadyInUseError,
    InvalidInviteCodeError,
    PasswordCompromisedError,
    WeakPasswordError,
)
from app.auth.hashing import hash_password
from app.auth.password_strength import is_breached_password
from app.auth.repository import UserCredentialLookup, UserRegistrationRepository
from app.auth.service import AuthService
from app.auth.username import derive_unique_username
from app.core.unit_of_work import UnitOfWork

MINIMUM_PASSWORD_LENGTH = 12
"""Raised from ADR-011's original 8 (2026-10-06, external security review) - NIST 800-63B
favors length over complexity rules, and registration is now open to the public, not just
friend-testing.
"""


class RegisterUserUseCase:
    """Self-service registration (ADR-011), additive alongside the existing pre-provisioned
    account (`sync_configured_user`, ADR-010 Decision item 1) - registration never touches or
    replaces that mechanism, it only creates additional `User` rows the same shape produces.

    Deliberately does not create an Agent Workspace - that remains the existing, separate
    onboarding flow (`POST /agents`). Registration's only job is the `User` row and a session
    token, mirroring exactly what a subsequent `POST /auth/login` would return.
    """

    def __init__(
        self,
        user_lookup: UserCredentialLookup,
        user_registration: UserRegistrationRepository,
        auth_service: AuthService,
        unit_of_work: UnitOfWork,
        *,
        required_invite_code: str | None,
        is_breached: Callable[[str], bool] = is_breached_password,
        email_verification: RequestEmailVerificationUseCase | None = None,
    ) -> None:
        self._users = user_lookup
        self._registration = user_registration
        self._auth_service = auth_service
        self._uow = unit_of_work
        self._required_invite_code = required_invite_code
        self._is_breached = is_breached
        # None in tests that don't care about email verification (most registration unit
        # tests); DI (get_register_user_use_case) always wires a real instance in production.
        self._email_verification = email_verification

    def execute(self, *, email: str, password: str, invite_code: str | None) -> str:
        """Returns a raw session token, exactly like `AuthService.login` - the caller is
        registered and logged in in one step, per ADR-011 Decision item 1.

        Collects an email, not a username (2026-10-06, external security review) - a username
        is still synthesized server-side (derive_unique_username) to satisfy the `users.username`
        NOT NULL UNIQUE column, mirroring exactly what Google Sign-In already does for its own
        accounts, but it is never shown to the caller as their real identity.
        """
        if self._required_invite_code and invite_code != self._required_invite_code:
            raise InvalidInviteCodeError()

        if len(password) < MINIMUM_PASSWORD_LENGTH:
            raise WeakPasswordError(minimum_length=MINIMUM_PASSWORD_LENGTH)

        if self._is_breached(password):
            raise PasswordCompromisedError()

        if self._users.get_by_email(email) is not None:
            raise EmailAlreadyInUseError()

        username = derive_unique_username(email, users=self._users)
        try:
            user = self._registration.create(
                username=username, password_hash=hash_password(password), email=email, email_verified=False
            )
            self._uow.commit()
        except IntegrityError:
            # A real race, not just a defensive precaution: the get_by_email check above and
            # this insert are two separate statements, so a second registration for the same
            # email arriving in that narrow window hits the `users.email` UNIQUE constraint
            # instead of the check above. Translated to the same domain exception the check
            # would have raised, rather than leaking a raw 500.
            self._uow.rollback()
            raise EmailAlreadyInUseError() from None
        except Exception:
            self._uow.rollback()
            raise

        if self._email_verification is not None:
            self._email_verification.execute(user_id=user.user_id)

        # Reuses AuthService.login's own public behavior wholesale (re-verifying the
        # just-set password) rather than duplicating session-token creation here - the same
        # "one real mechanism, no parallel path" discipline ADR-010 already established.
        return self._auth_service.login(username=username, password=password)
