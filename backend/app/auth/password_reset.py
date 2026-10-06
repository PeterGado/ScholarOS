import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.auth.exceptions import InvalidResetTokenError, WeakPasswordError
from app.auth.hashing import hash_password
from app.auth.registration import MINIMUM_PASSWORD_LENGTH
from app.auth.repository import (
    AuthSessionRepository,
    PasswordResetTokenRepository,
    UserAccountRepository,
    UserCredentialLookup,
)
from app.auth.tokens import generate_session_token, hash_session_token
from app.core.unit_of_work import UnitOfWork
from app.email.exceptions import EmailSendError
from app.email.resend import send_email

logger = logging.getLogger(__name__)


class RequestPasswordResetUseCase:
    """Starts a password reset (2026-10-06): issues a single-use, time-limited token for the
    account matching the supplied email (if any) and emails a reset link to it.

    Deliberately returns the same nothing regardless of whether the email matched a real
    account, and regardless of whether the email actually sent - `execute()`'s caller (the
    route) must show an identical response either way, or the response shape itself becomes a
    username/email-enumeration oracle (the same reasoning InvalidCredentialsError already
    applies to login). A genuine database failure still propagates; only "no such account" and
    "the email provider failed" are swallowed here, not "the write failed".
    """

    def __init__(
        self,
        user_lookup: UserCredentialLookup,
        reset_tokens: PasswordResetTokenRepository,
        unit_of_work: UnitOfWork,
        *,
        token_ttl_minutes: int,
        frontend_base_url: str,
        resend_api_key: str | None,
        from_address: str,
        email_sender: Callable[..., None] = send_email,
    ) -> None:
        self._users = user_lookup
        self._reset_tokens = reset_tokens
        self._uow = unit_of_work
        self._token_ttl_minutes = token_ttl_minutes
        self._frontend_base_url = frontend_base_url
        self._resend_api_key = resend_api_key
        self._from_address = from_address
        self._email_sender = email_sender

    def execute(self, *, email: str) -> None:
        user = self._users.get_by_email(email)
        if user is None:
            return

        raw_token = generate_session_token()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self._token_ttl_minutes)
        try:
            self._reset_tokens.create(
                user_id=user.user_id, token_hash=hash_session_token(raw_token), expires_at=expires_at
            )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        reset_link = f"{self._frontend_base_url}/reset-password?token={raw_token}"
        html = (
            f"<p>Click the link below to reset your ScholarOS password. "
            f"This link expires in {self._token_ttl_minutes} minutes and can only be used once.</p>"
            f'<p><a href="{reset_link}">{reset_link}</a></p>'
            f"<p>If you didn't request this, you can safely ignore this email.</p>"
        )
        try:
            self._email_sender(
                to=email,
                subject="Reset your ScholarOS password",
                html=html,
                api_key=self._resend_api_key,
                from_address=self._from_address,
            )
        except EmailSendError as exc:
            # Swallowed deliberately - see this class's own docstring. The token still exists
            # and is still valid; a user who never receives the email has no way to use it
            # regardless, but the route's response must not betray that sending failed.
            logger.warning("Password reset email failed to send for user %s: %s", user.user_id, exc)


class ConfirmPasswordResetUseCase:
    """Completes a password reset (2026-10-06): verifies the token, sets the new password, and
    ends every other active session for the account - a successful reset should not leave an
    attacker's existing session (the whole reason the user is resetting) still valid.
    """

    def __init__(
        self,
        reset_tokens: PasswordResetTokenRepository,
        user_account: UserAccountRepository,
        auth_sessions: AuthSessionRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._reset_tokens = reset_tokens
        self._user_account = user_account
        self._auth_sessions = auth_sessions
        self._uow = unit_of_work

    def execute(self, *, raw_token: str, new_password: str) -> None:
        if len(new_password) < MINIMUM_PASSWORD_LENGTH:
            raise WeakPasswordError(minimum_length=MINIMUM_PASSWORD_LENGTH)

        token = self._reset_tokens.get_by_token_hash(hash_session_token(raw_token))
        if token is None or not token.is_valid(now=datetime.now(timezone.utc)):
            raise InvalidResetTokenError()

        try:
            self._user_account.update_password_hash(token.user_id, hash_password(new_password))
            self._reset_tokens.mark_used(token)
            self._auth_sessions.end_all_for_user(token.user_id)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
