import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.auth.exceptions import InvalidVerificationTokenError
from app.auth.repository import (
    EmailVerificationTokenRepository,
    UserAccountRepository,
    UserCredentialLookup,
)
from app.auth.tokens import generate_session_token, hash_session_token
from app.core.unit_of_work import UnitOfWork
from app.email.exceptions import EmailSendError
from app.email.resend import send_email

logger = logging.getLogger(__name__)


class RequestEmailVerificationUseCase:
    """Starts (or restarts) email verification (2026-10-06, external security review): issues
    a single-use, time-limited token for the given user and emails a confirmation link.

    Unlike RequestPasswordResetUseCase, the caller already knows the user_id - either fresh off
    a password registration, or an authenticated resend from Settings - so there is no
    email-enumeration concern here. A send failure is still swallowed (the same reasoning
    RequestPasswordResetUseCase's own docstring gives: the token remains valid regardless, and
    a resend exists for exactly this case), so a flaky email provider never blocks registration
    itself or turns a resend click into a visible error.
    """

    def __init__(
        self,
        user_lookup: UserCredentialLookup,
        verification_tokens: EmailVerificationTokenRepository,
        unit_of_work: UnitOfWork,
        *,
        token_ttl_minutes: int,
        frontend_base_url: str,
        resend_api_key: str | None,
        from_address: str,
        email_sender: Callable[..., None] = send_email,
    ) -> None:
        self._users = user_lookup
        self._verification_tokens = verification_tokens
        self._uow = unit_of_work
        self._token_ttl_minutes = token_ttl_minutes
        self._frontend_base_url = frontend_base_url
        self._resend_api_key = resend_api_key
        self._from_address = from_address
        self._email_sender = email_sender

    def execute(self, *, user_id: int) -> None:
        user = self._users.get_by_id(user_id)
        assert user is not None, f"user_id {user_id} came from a verified session but has no User row"
        if user.email is None:
            # Nothing to verify - a password account with no email on file yet. Not expected
            # from registration (email is required there now), but a defensive no-op rather
            # than an assertion, since a resend could in principle be called for any user_id.
            return

        raw_token = generate_session_token()
        expires_at = datetime.now(UTC) + timedelta(minutes=self._token_ttl_minutes)
        try:
            self._verification_tokens.create(
                user_id=user_id, token_hash=hash_session_token(raw_token), expires_at=expires_at
            )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        verify_link = f"{self._frontend_base_url}/verify-email?token={raw_token}"
        html = (
            f"<p>Click the link below to verify your ScholarOS email address. "
            f"This link expires in {self._token_ttl_minutes} minutes and can only be used once.</p>"
            f'<p><a href="{verify_link}">{verify_link}</a></p>'
            f"<p>If you didn't create a ScholarOS account, you can safely ignore this email.</p>"
        )
        try:
            self._email_sender(
                to=user.email,
                subject="Verify your ScholarOS email",
                html=html,
                api_key=self._resend_api_key,
                from_address=self._from_address,
            )
        except EmailSendError as exc:
            logger.warning("Verification email failed to send for user %s: %s", user_id, exc)


class ConfirmEmailVerificationUseCase:
    """Completes email verification (2026-10-06): verifies the token and marks the account's
    email as confirmed, unblocking document upload and chat for it.
    """

    def __init__(
        self,
        verification_tokens: EmailVerificationTokenRepository,
        user_account: UserAccountRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._verification_tokens = verification_tokens
        self._user_account = user_account
        self._uow = unit_of_work

    def execute(self, *, raw_token: str) -> None:
        token = self._verification_tokens.get_by_token_hash(hash_session_token(raw_token))
        if token is None or not token.is_valid(now=datetime.now(UTC)):
            raise InvalidVerificationTokenError()

        try:
            self._user_account.mark_email_verified(token.user_id)
            self._verification_tokens.mark_used(token)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
