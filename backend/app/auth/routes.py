from fastapi import APIRouter, Depends, Request, status

from app.api.exception_handlers import ErrorResponse
from app.auth.dependencies import extract_bearer_token
from app.auth.google_sign_in import GoogleSignInUseCase
from app.auth.registration import RegisterUserUseCase
from app.auth.schemas import GoogleSignInRequest, LoginRequest, RegisterRequest, TokenResponse
from app.auth.service import AuthService
from app.core.dependencies import get_auth_service, get_google_sign_in_use_case, get_register_user_use_case
from app.core.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or incorrect invite code (only when one is configured)."},
        409: {"model": ErrorResponse, "description": "That username is already taken."},
        422: {"model": ErrorResponse, "description": "Malformed request body, or password shorter than the minimum."},
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

    No business logic lives here: username/password validation, the optional invite-code
    check, and account creation all happen in RegisterUserUseCase; exceptions are translated
    to HTTP responses by the handlers registered in app.api.exception_handlers.
    """
    token = use_case.execute(username=payload.username, password=payload.password, invite_code=payload.invite_code)
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
