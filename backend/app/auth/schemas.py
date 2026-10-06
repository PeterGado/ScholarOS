from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Request body for POST /auth/login. Field name stays `username` for wire compatibility,
    but AuthService.login (2026-10-06) accepts either a legacy username or an email here - the
    caller sends whatever identifier the user typed.
    """

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    """Request body for POST /auth/register (ADR-011). Collects an email, not a username
    (2026-10-06, external security review) - a username is still synthesized server-side to
    satisfy the `users.username` column, but it is never user-chosen or shown as the account's
    real identity. invite_code is always accepted, even when REGISTRATION_INVITE_CODE isn't
    configured - the frontend never needs to know whether one is required; RegisterUserUseCase
    simply ignores it when no code is configured.
    """

    email: EmailStr
    password: str = Field(..., min_length=1)
    invite_code: str | None = None


class GoogleSignInRequest(BaseModel):
    """Request body for POST /auth/google (2026-09-20). invite_code is always accepted, same
    reasoning as RegisterRequest's own - it's only enforced for a brand-new account when
    REGISTRATION_INVITE_CODE is configured; a returning Google user's is ignored entirely.
    """

    id_token: str = Field(..., min_length=1)
    invite_code: str | None = None


class TokenResponse(BaseModel):
    """Response body for POST /auth/login. Deliberately contains nothing but the token -
    no session_id, no timestamps, no internal fields (05_Constraints_and_Integrity.md §17).
    """

    access_token: str
    token_type: str = "bearer"


class ProfileResponse(BaseModel):
    """Response body for GET /auth/profile - the account info the frontend needs to display
    (e.g. the Settings page), kept separate from TokenResponse and the 204-only GET /auth/me
    so neither of those deliberately-minimal contracts has to grow a body.

    `email` (2026-10-06) is nullable: registration never collects one, so most accounts have
    none until a user explicitly adds one via PUT /auth/email.
    """

    username: str
    email: str | None = None
    email_verified: bool = True
    google_connected: bool = False
    has_password: bool = True


class UpdateEmailRequest(BaseModel):
    """Request body for PUT /auth/email (2026-10-06, Settings) - what makes password reset
    reachable for a username/password account, since registration itself never asks for one.
    """

    email: EmailStr


class RequestPasswordResetRequest(BaseModel):
    """Request body for POST /auth/password-reset/request (2026-10-06)."""

    email: EmailStr


class ConfirmPasswordResetRequest(BaseModel):
    """Request body for POST /auth/password-reset/confirm (2026-10-06). `token` is the raw,
    single-use token from the emailed reset link - never the hash stored at rest.
    """

    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


class ConfirmEmailVerificationRequest(BaseModel):
    """Request body for POST /auth/email-verification/confirm (2026-10-06). `token` is the raw,
    single-use token from the emailed verification link - never the hash stored at rest.
    """

    token: str = Field(..., min_length=1)


class ConnectGoogleRequest(BaseModel):
    """Request body for POST /auth/google/connect (2026-10-06, Settings -> Security). Same
    `id_token` shape as GoogleSignInRequest, minus invite_code - connecting an already-
    authenticated account is never gated by one.
    """

    id_token: str = Field(..., min_length=1)


class SetPasswordRequest(BaseModel):
    """Request body for POST /auth/password/set (2026-10-06, Settings -> Security) - lets a
    Google-origin account set a real password for the first time.
    """

    password: str = Field(..., min_length=1)
