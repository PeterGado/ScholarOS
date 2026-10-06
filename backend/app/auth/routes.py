from fastapi import APIRouter, Depends, Request, status

from app.api.exception_handlers import ErrorResponse
from app.auth.account import UpdateEmailUseCase
from app.auth.account_linking import ConnectGoogleAccountUseCase, SetPasswordUseCase
from app.auth.dependencies import extract_bearer_token
from app.auth.email_verification import ConfirmEmailVerificationUseCase, RequestEmailVerificationUseCase
from app.auth.google_sign_in import GoogleSignInUseCase
from app.auth.password_reset import ConfirmPasswordResetUseCase, RequestPasswordResetUseCase
from app.auth.registration import RegisterUserUseCase
from app.auth.schemas import (
    ConfirmEmailVerificationRequest,
    ConfirmPasswordResetRequest,
    ConnectGoogleRequest,
    GoogleSignInRequest,
    LoginRequest,
    ProfileResponse,
    RegisterRequest,
    RequestPasswordResetRequest,
    SetPasswordRequest,
    TokenResponse,
    UpdateEmailRequest,
)
from app.auth.service import AuthService
from app.core.dependencies import (
    get_auth_service,
    get_confirm_email_verification_use_case,
    get_confirm_password_reset_use_case,
    get_connect_google_account_use_case,
    get_current_user_id,
    get_google_sign_in_use_case,
    get_register_user_use_case,
    get_request_email_verification_use_case,
    get_request_password_reset_use_case,
    get_set_password_use_case,
    get_update_email_use_case,
)
from app.core.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or incorrect invite code (only when one is configured)."},
        409: {"model": ErrorResponse, "description": "That email is already associated with another account."},
        422: {"model": ErrorResponse, "description": "Malformed request body, or password shorter than the minimum, or appears in a known data breach."},
        429: {"model": ErrorResponse, "description": "Too many registration attempts from this client."},
    },
)
# 2026-09-19 production security pass: registration was previously unlimited - a publicly
# reachable account-creation endpoint with zero throttling. 5/minute per IP is generous for a
# real user, tight for a scripted account-creation loop.
@limiter.limit("5/minute")
def register(
    request: Request,
    payload: RegisterRequest,
    use_case: RegisterUserUseCase = Depends(get_register_user_use_case),
) -> TokenResponse:
    """Creates a new account and immediately returns a usable session token (ADR-011) - the
    caller is registered and logged in in one step, mirroring /auth/login's own response shape
    exactly. 201, not 200: a real resource (the account) was created, unlike login.

    No business logic lives here: email/password validation, the optional invite-code check,
    and account creation all happen in RegisterUserUseCase; exceptions are translated to HTTP
    responses by the handlers registered in app.api.exception_handlers.
    """
    token = use_case.execute(email=payload.email, password=payload.password, invite_code=payload.invite_code)
    return TokenResponse(access_token=token)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid username or password."},
        422: {
            "model": ErrorResponse,
            "description": "Malformed request body. Uses FastAPI's own validation error shape instead.",
        },
        429: {"model": ErrorResponse, "description": "Too many login attempts from this client."},
    },
)
# 2026-09-19 production security pass: confirmed live (20 rapid wrong-password attempts, zero
# throttling) before this fix. 10/minute per IP stops a brute-force loop without blocking a
# real user who mistypes a password a few times.
@limiter.limit("10/minute")
def login(
    request: Request,
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Verify the provisioned account's credentials and issue a session token (ADR-010).

    No business logic lives here: credential verification and session creation happen in
    AuthService; exceptions are translated to HTTP responses by the handlers registered in
    app.api.exception_handlers. 200, not 201: a client-meaningful login response, not a
    resource-creation response, even though a Session row is created server-side.
    """
    token = auth_service.login(username=payload.username, password=payload.password)
    return TokenResponse(access_token=token)


@router.post(
    "/google",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid Google sign-in token, or (new accounts only) missing/incorrect invite code."},
        409: {"model": ErrorResponse, "description": "An account with this email already exists - sign in with your password instead."},
        429: {"model": ErrorResponse, "description": "Too many sign-in attempts from this client."},
        503: {"model": ErrorResponse, "description": "Google sign-in is not configured."},
    },
)
# Same rate limit as /auth/login - this is as much an auth entrypoint as that route.
@limiter.limit("10/minute")
def google_sign_in(
    request: Request,
    payload: GoogleSignInRequest,
    use_case: GoogleSignInUseCase = Depends(get_google_sign_in_use_case),
) -> TokenResponse:
    """Sign in (or, for a first-time Google identity, register) via a Google Identity Services
    ID token (2026-09-20) - added alongside, not instead of, username+password (ADR-010) and
    self-service registration (ADR-011). 200, not 201: whether this call created an account or
    just logged in an existing one is not something the response distinguishes, mirroring how
    the client itself never needs to know in advance which case it is.

    No business logic lives here: token verification, the returning-vs-new-account branch, the
    invite-code gate, and session creation all happen in GoogleSignInUseCase/AuthService;
    exceptions are translated to HTTP responses by the handlers registered in
    app.api.exception_handlers.
    """
    token = use_case.execute(id_token=payload.id_token, invite_code=payload.invite_code)
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
    },
)
def get_current_session(
    user_id: int = Depends(get_current_user_id),
) -> None:
    """Verifies the presented bearer token still identifies a real, active session (2026-09-30,
    added after a real frontend bug: the client tracked "logged in" as merely holding *a* token
    in local storage, never confirming it was still valid - a stale or already-ended session
    silently skipped the landing page and bounced into a broken authenticated app state instead,
    with no way back to the landing page short of manually clearing browser storage). No body:
    the status code alone (204 valid, 401 not) is the only signal a caller needs.
    """
    return None


@router.get(
    "/profile",
    response_model=ProfileResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
    },
)
def get_profile(
    user_id: int = Depends(get_current_user_id),
    auth_service: AuthService = Depends(get_auth_service),
) -> ProfileResponse:
    """The one piece of account info the frontend needs to display (e.g. the Settings page) -
    separate from the 204-only GET /auth/me so that endpoint's "status code is the only
    signal" contract stays true, and separate from TokenResponse so login/register stay as
    minimal as 05_Constraints_and_Integrity.md §17 documents them.
    """
    google_connected, has_password = auth_service.get_sign_in_methods(user_id)
    return ProfileResponse(
        username=auth_service.get_username(user_id),
        email=auth_service.get_email(user_id),
        email_verified=auth_service.get_email_verified(user_id),
        google_connected=google_connected,
        has_password=has_password,
    )


@router.put(
    "/email",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        409: {"model": ErrorResponse, "description": "That email is already associated with another account."},
        422: {"model": ErrorResponse, "description": "Malformed request body, or not a valid email address."},
    },
)
def update_email(
    payload: UpdateEmailRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: UpdateEmailUseCase = Depends(get_update_email_use_case),
) -> None:
    """Adds or changes the email on the authenticated user's own account (2026-10-06,
    Settings) - the only way a username/password account ever gets an email on file, since
    registration itself never collects one. Primarily what makes POST /auth/password-reset/
    request reachable for that account.
    """
    use_case.execute(user_id=user_id, email=payload.email)


@router.post(
    "/google/connect",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Missing/malformed/ended session, or an invalid Google sign-in token."},
        409: {"model": ErrorResponse, "description": "This Google account is already connected to a different ScholarOS account."},
        503: {"model": ErrorResponse, "description": "Google sign-in is not configured."},
    },
)
def connect_google_account(
    payload: ConnectGoogleRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: ConnectGoogleAccountUseCase = Depends(get_connect_google_account_use_case),
) -> None:
    """Links the authenticated user's own account to a Google identity (2026-10-06,
    Settings -> Security -> Connected accounts) - the OWASP-recommended linking path: requires
    an authenticated session and validates the new identity before linking it, never an
    automatic match at sign-in time.
    """
    use_case.execute(user_id=user_id, id_token=payload.id_token)


@router.post(
    "/password/set",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        422: {"model": ErrorResponse, "description": "Password shorter than the minimum, or appears in a known data breach."},
    },
)
def set_password(
    payload: SetPasswordRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: SetPasswordUseCase = Depends(get_set_password_use_case),
) -> None:
    """Sets a real password on the authenticated user's own account for the first time
    (2026-10-06, Settings -> Security -> Connected accounts) - for a Google-origin account whose
    `password_hash` still defaults to `""` (never verifies), enabling email/password sign-in as
    a second path into the same account.
    """
    use_case.execute(user_id=user_id, password=payload.password)


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        422: {"model": ErrorResponse, "description": "Malformed request body, or not a valid email address."},
        429: {"model": ErrorResponse, "description": "Too many requests from this client."},
    },
)
# Same shape as /auth/login's own rate limit reasoning - a publicly reachable endpoint that
# triggers a real email send per call must not be left unthrottled.
@limiter.limit("5/minute")
def request_password_reset(
    request: Request,
    payload: RequestPasswordResetRequest,
    use_case: RequestPasswordResetUseCase = Depends(get_request_password_reset_use_case),
) -> None:
    """Starts a password reset (2026-10-06). Always 204, regardless of whether the email
    matched a real account or whether sending actually succeeded - RequestPasswordResetUseCase
    itself swallows both cases (see its own docstring) specifically so this response can never
    be used to enumerate which emails have an account here.
    """
    use_case.execute(email=payload.email)


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "The reset token is invalid, expired, or already used."},
        422: {"model": ErrorResponse, "description": "Malformed request body, or password shorter than the minimum."},
        429: {"model": ErrorResponse, "description": "Too many attempts from this client."},
    },
)
# A token-guessing surface, same reasoning as /auth/login's own throttle.
@limiter.limit("10/minute")
def confirm_password_reset(
    request: Request,
    payload: ConfirmPasswordResetRequest,
    use_case: ConfirmPasswordResetUseCase = Depends(get_confirm_password_reset_use_case),
) -> None:
    """Completes a password reset (2026-10-06): verifies the token, sets the new password, and
    ends every other active session for the account.
    """
    use_case.execute(raw_token=payload.token, new_password=payload.new_password)


@router.post(
    "/email-verification/request",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        429: {"model": ErrorResponse, "description": "Too many requests from this client."},
    },
)
# Same rate-limit reasoning as /auth/password-reset/request - a real email send per call.
@limiter.limit("5/minute")
def request_email_verification(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    use_case: RequestEmailVerificationUseCase = Depends(get_request_email_verification_use_case),
) -> None:
    """Resends the verification link to the authenticated user's own email (2026-10-06,
    Settings' Connected accounts card) - also called once automatically right after a password
    registration. Always 204: RequestEmailVerificationUseCase itself swallows a send failure
    (see its own docstring), and there is no enumeration concern since the caller is already
    authenticated as the account being verified.
    """
    use_case.execute(user_id=user_id)


@router.post(
    "/email-verification/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "The verification token is invalid, expired, or already used."},
        429: {"model": ErrorResponse, "description": "Too many attempts from this client."},
    },
)
# A token-guessing surface, same reasoning as /auth/password-reset/confirm's own throttle.
@limiter.limit("10/minute")
def confirm_email_verification(
    request: Request,
    payload: ConfirmEmailVerificationRequest,
    use_case: ConfirmEmailVerificationUseCase = Depends(get_confirm_email_verification_use_case),
) -> None:
    """Completes email verification (2026-10-06): verifies the token and unblocks document
    upload and chat for the account.
    """
    use_case.execute(raw_token=payload.token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Missing, malformed, unknown, or already-ended session.",
        },
    },
)
def logout(
    raw_token: str = Depends(extract_bearer_token),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """End the session identified by the presented bearer token (ADR-010).

    No business logic lives here: session lookup and termination happen in AuthService.
    204, no body: nothing meaningful to return for a successful logout.
    """
    auth_service.logout(raw_token)
