from fastapi import APIRouter, Depends, status

from app.api.exception_handlers import ErrorResponse
from app.auth.dependencies import extract_bearer_token
from app.auth.schemas import LoginRequest, TokenResponse
from app.auth.service import AuthService
from app.core.dependencies import get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


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
    },
)
def login(
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
