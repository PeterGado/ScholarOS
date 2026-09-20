from typing import Any, Callable

from sqlalchemy.exc import IntegrityError

from app.auth.exceptions import (
    GoogleAccountEmailConflictError,
    GoogleSignInNotConfiguredError,
    InvalidGoogleTokenError,
    InvalidInviteCodeError,
)
from app.auth.repository import UserCredentialLookup, UserRegistrationRepository
from app.auth.service import AuthService
from app.core.unit_of_work import UnitOfWork

TokenVerifier = Callable[..., dict[str, Any]]


class GoogleSignInUseCase:
    """Google Sign-In (2026-09-20), added alongside the existing username+password login
    (ADR-010) and self-service registration (ADR-011) - not a replacement for either.

    A returning Google user (an existing `google_subject` match) is logged in with no invite
    code check at all, exactly like a returning password user re-entering /auth/login never
    re-supplies one. A brand-new Google account is held to the same REGISTRATION_INVITE_CODE
    gate RegisterUserUseCase already enforces, so this can't become a backdoor around
    friends-only testing.
    """

    def __init__(
        self,
        user_lookup: UserCredentialLookup,
        user_registration: UserRegistrationRepository,
        auth_service: AuthService,
        unit_of_work: UnitOfWork,
        verify_id_token: TokenVerifier,
        *,
        required_invite_code: str | None,
        google_client_id: str | None,
    ) -> None:
        self._users = user_lookup
        self._registration = user_registration
        self._auth_service = auth_service
        self._uow = unit_of_work
        self._verify_id_token = verify_id_token
        self._required_invite_code = required_invite_code
        self._google_client_id = google_client_id

    def execute(self, *, id_token: str, invite_code: str | None) -> str:
        if self._google_client_id is None:
            raise GoogleSignInNotConfiguredError()

        try:
            claims = self._verify_id_token(id_token, client_id=self._google_client_id)
        except ValueError:
            raise InvalidGoogleTokenError() from None

        google_subject = claims["sub"]
        existing = self._users.get_by_google_subject(google_subject)
        if existing is not None:
            return self._auth_service.create_session_for_verified_identity(user_id=existing.user_id)

        if self._required_invite_code and invite_code != self._required_invite_code:
            raise InvalidInviteCodeError()

        email = claims.get("email")
        # Only a Google-verified email is treated as a real collision signal - an unverified
        # one proves nothing about who actually controls that address.
        if email and claims.get("email_verified") and self._users.get_by_email(email) is not None:
            raise GoogleAccountEmailConflictError()

        username = self._derive_unique_username(email or google_subject)
        try:
            user = self._registration.create_from_google(
                username=username,
                email=email,
                google_subject=google_subject,
                display_name=claims.get("name"),
            )
            self._uow.commit()
        except IntegrityError:
            # A real race (two concurrent first-time sign-ins for the same Google identity
            # arriving in the narrow window between the get_by_google_subject check above and
            # this insert), not just a defensive precaution - mirrors RegisterUserUseCase's own
            # documented username race. The account now genuinely exists (created by the other
            # request), so log in rather than surface an error for what is actually success.
            self._uow.rollback()
            existing_after_race = self._users.get_by_google_subject(google_subject)
            if existing_after_race is not None:
                return self._auth_service.create_session_for_verified_identity(user_id=existing_after_race.user_id)
            raise
        except Exception:
            self._uow.rollback()
            raise
        return self._auth_service.create_session_for_verified_identity(user_id=user.user_id)

    def _derive_unique_username(self, seed: str) -> str:
        base = seed.split("@")[0] or "user"
        candidate, suffix = base, 1
        while self._users.get_by_username(candidate) is not None:
            suffix += 1
            candidate = f"{base}{suffix}"
        return candidate
