from typing import Any, Callable

from app.auth.exceptions import (
    GoogleAccountAlreadyLinkedError,
    GoogleSignInNotConfiguredError,
    InvalidGoogleTokenError,
    PasswordCompromisedError,
    WeakPasswordError,
)
from app.auth.hashing import hash_password
from app.auth.password_strength import is_breached_password
from app.auth.registration import MINIMUM_PASSWORD_LENGTH
from app.auth.repository import UserAccountRepository, UserCredentialLookup
from app.core.unit_of_work import UnitOfWork

TokenVerifier = Callable[..., dict[str, Any]]


class ConnectGoogleAccountUseCase:
    """Links an already-authenticated password account to a Google identity (2026-10-06,
    Settings -> Security -> Connected accounts) - the OWASP-recommended linking path the
    external security review asked for: requires an authenticated session and validates the
    new identity (a real, signature-verified Google ID token) before linking it, rather than
    ever auto-linking on an email match at sign-in time (see GoogleAccountEmailConflictError's
    own docstring for why that path is deliberately closed).

    Deliberately does not touch `email` - linking only connects a second credential to the
    account, it never merges or overwrites profile data.
    """

    def __init__(
        self,
        user_lookup: UserCredentialLookup,
        user_account: UserAccountRepository,
        unit_of_work: UnitOfWork,
        verify_id_token: TokenVerifier,
        *,
        google_client_id: str | None,
    ) -> None:
        self._users = user_lookup
        self._user_account = user_account
        self._uow = unit_of_work
        self._verify_id_token = verify_id_token
        self._google_client_id = google_client_id

    def execute(self, *, user_id: int, id_token: str) -> None:
        if self._google_client_id is None:
            raise GoogleSignInNotConfiguredError()

        try:
            claims = self._verify_id_token(id_token, client_id=self._google_client_id)
        except ValueError:
            raise InvalidGoogleTokenError() from None

        google_subject = claims["sub"]
        existing = self._users.get_by_google_subject(google_subject)
        if existing is not None and existing.user_id != user_id:
            raise GoogleAccountAlreadyLinkedError()

        try:
            self._user_account.set_google_subject(user_id, google_subject)
            # Google's own OIDC claim is authoritative, same reasoning as a brand-new Google
            # sign-in (GoogleSignInUseCase) - connecting a Google account whose claim confirms
            # the email is itself proof of control, independent of whatever verification state
            # the account's own `email` field already had.
            if claims.get("email_verified"):
                self._user_account.mark_email_verified(user_id)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise


class SetPasswordUseCase:
    """Lets an already-authenticated Google-origin account (whose `password_hash` defaults to
    `""`, which never verifies - see the User model's own comment) set a real password for the
    first time (2026-10-06, Settings -> Security -> Connected accounts), enabling email/password
    sign-in as a second path into the same account. Same strength checks as registration.
    """

    def __init__(
        self,
        user_account: UserAccountRepository,
        unit_of_work: UnitOfWork,
        *,
        is_breached: Callable[[str], bool] = is_breached_password,
    ) -> None:
        self._user_account = user_account
        self._uow = unit_of_work
        self._is_breached = is_breached

    def execute(self, *, user_id: int, password: str) -> None:
        if len(password) < MINIMUM_PASSWORD_LENGTH:
            raise WeakPasswordError(minimum_length=MINIMUM_PASSWORD_LENGTH)

        if self._is_breached(password):
            raise PasswordCompromisedError()

        try:
            self._user_account.update_password_hash(user_id, hash_password(password))
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
