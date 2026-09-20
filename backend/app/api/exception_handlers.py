from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded

from app.ai.exceptions import ProviderConfigurationError, ProviderRequestError
from app.auth.exceptions import (
    GoogleAccountEmailConflictError,
    GoogleSignInNotConfiguredError,
    InvalidCredentialsError,
    InvalidGoogleTokenError,
    InvalidInviteCodeError,
    InvalidSessionError,
    UsernameAlreadyTakenError,
    WeakPasswordError,
)
from app.core.exceptions import ScholarOSError, UploadTooLargeError
from app.modules.agent.domain.exceptions import AgentAlreadyExistsForUserError, AgentNotFoundForUserError
from app.modules.document.domain.exceptions import (
    DocumentCannotBeDeletedError,
    DocumentCannotBeRetriedError,
    EmptyDocumentContentError,
    InvalidDocumentFormatError,
    InvalidDocumentTitleError,
    ResearchDocumentNotFoundError,
    TooManyResearchDocumentsError,
)
from app.modules.project.domain.exceptions import (
    InvalidProjectTitleError,
    InvalidProjectTopicError,
    ProjectAlreadyExistsForAgentError,
    ProjectNotFoundError,
)
from app.modules.writing.domain.exceptions import (
    ChatReplyCannotBeRetriedError,
    ChatReplyWorkItemNotFoundError,
    ConversationNotFoundError,
    InvalidStyleSampleReferenceError,
    MemoryRecordAlreadySupersededError,
    MemoryRecordNotFoundError,
    NoUsableWritingStyleSamplesError,
    TooManyWritingStyleSamplesError,
    UnusableWritingStyleSampleError,
    WritingProfileAlreadyExtractedError,
    WritingProfileNotFoundError,
)


class ErrorResponse(BaseModel):
    """Consistent error envelope for every non-2xx response this API returns."""

    error_type: str
    detail: str


def _respond(status_code: int, error_type: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error_type=error_type, detail=detail).model_dump(),
    )


async def _handle_conflict(request: Request, exc: Exception) -> JSONResponse:
    return _respond(status.HTTP_409_CONFLICT, type(exc).__name__, str(exc))


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    return _respond(status.HTTP_404_NOT_FOUND, type(exc).__name__, str(exc))


async def _handle_invalid_input(request: Request, exc: Exception) -> JSONResponse:
    return _respond(status.HTTP_422_UNPROCESSABLE_CONTENT, type(exc).__name__, str(exc))


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    return _respond(status.HTTP_401_UNAUTHORIZED, type(exc).__name__, str(exc))


async def _handle_storage_failure(request: Request, exc: Exception) -> JSONResponse:
    # Deliberately does not forward str(exc): OSError messages can include filesystem paths,
    # which are a persistence implementation detail and must not reach the client.
    return _respond(status.HTTP_500_INTERNAL_SERVER_ERROR, "StorageError", "Storage operation failed.")


async def _handle_provider_unavailable(request: Request, exc: Exception) -> JSONResponse:
    # First route-reachable AI provider exceptions (Stage 8's search endpoint); never forward
    # str(exc) for ProviderConfigurationError - it never contains a secret itself, but a
    # generic message keeps failure modes indistinguishable to the client either way.
    return _respond(status.HTTP_503_SERVICE_UNAVAILABLE, type(exc).__name__, "The AI provider is not available.")


async def _handle_provider_request_failure(request: Request, exc: Exception) -> JSONResponse:
    return _respond(status.HTTP_502_BAD_GATEWAY, type(exc).__name__, "The AI provider request failed.")


async def _handle_service_unavailable(request: Request, exc: Exception) -> JSONResponse:
    # Unlike _handle_provider_unavailable, str(exc) is safe to forward here - every exception
    # routed through this handler (currently just GoogleSignInNotConfiguredError) carries a
    # fixed, hardcoded message with no request-derived or secret content.
    return _respond(status.HTTP_503_SERVICE_UNAVAILABLE, type(exc).__name__, str(exc))


async def _handle_payload_too_large(request: Request, exc: Exception) -> JSONResponse:
    return _respond(status.HTTP_413_CONTENT_TOO_LARGE, type(exc).__name__, str(exc))


async def _handle_rate_limit_exceeded(request: Request, exc: Exception) -> JSONResponse:
    # exc is a RateLimitExceeded (an HTTPException subclass); still typed as the base Exception
    # here to match every other handler's signature registered via app.add_exception_handler.
    # Deliberately not using slowapi's own header injection (Limiter.headers_enabled) - turning
    # that on makes slowapi try to inject headers into every *successful* response too, which
    # crashes because a FastAPI endpoint returns a Pydantic model/dict, not a Starlette Response
    # (FastAPI only builds the real Response afterward). Retry-After is computed directly from
    # the exceeded limit's own window instead - approximate (the window length, not the exact
    # remaining time), but accurate enough for a client's backoff and avoids that crash.
    response = _respond(status.HTTP_429_TOO_MANY_REQUESTS, "RateLimitExceeded", f"Rate limit exceeded: {exc.detail}")
    response.headers["Retry-After"] = str(exc.limit.limit.get_expiry())
    return response


async def _handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    """Fallback for any ScholarOSError subclass not given a more specific mapping above."""
    return _respond(status.HTTP_400_BAD_REQUEST, type(exc).__name__, str(exc))


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Deliberately does not forward str(exc) or any traceback - never expose internals for a
    # genuinely unanticipated failure.
    return _respond(status.HTTP_500_INTERNAL_SERVER_ERROR, "InternalError", "An unexpected internal error occurred.")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AgentAlreadyExistsForUserError, _handle_conflict)
    app.add_exception_handler(AgentNotFoundForUserError, _handle_not_found)
    app.add_exception_handler(ProjectAlreadyExistsForAgentError, _handle_conflict)
    app.add_exception_handler(ProjectNotFoundError, _handle_not_found)
    app.add_exception_handler(InvalidProjectTitleError, _handle_invalid_input)
    app.add_exception_handler(InvalidProjectTopicError, _handle_invalid_input)
    app.add_exception_handler(InvalidDocumentTitleError, _handle_invalid_input)
    app.add_exception_handler(InvalidDocumentFormatError, _handle_invalid_input)
    app.add_exception_handler(EmptyDocumentContentError, _handle_invalid_input)
    app.add_exception_handler(ResearchDocumentNotFoundError, _handle_not_found)
    app.add_exception_handler(DocumentCannotBeDeletedError, _handle_conflict)
    app.add_exception_handler(DocumentCannotBeRetriedError, _handle_conflict)
    app.add_exception_handler(TooManyResearchDocumentsError, _handle_conflict)
    app.add_exception_handler(InvalidStyleSampleReferenceError, _handle_not_found)
    app.add_exception_handler(NoUsableWritingStyleSamplesError, _handle_invalid_input)
    app.add_exception_handler(TooManyWritingStyleSamplesError, _handle_conflict)
    app.add_exception_handler(UnusableWritingStyleSampleError, _handle_invalid_input)
    app.add_exception_handler(WritingProfileAlreadyExtractedError, _handle_conflict)
    app.add_exception_handler(WritingProfileNotFoundError, _handle_not_found)
    app.add_exception_handler(ConversationNotFoundError, _handle_not_found)
    app.add_exception_handler(ChatReplyWorkItemNotFoundError, _handle_not_found)
    app.add_exception_handler(ChatReplyCannotBeRetriedError, _handle_conflict)
    app.add_exception_handler(MemoryRecordNotFoundError, _handle_not_found)
    app.add_exception_handler(MemoryRecordAlreadySupersededError, _handle_conflict)
    app.add_exception_handler(InvalidCredentialsError, _handle_unauthorized)
    app.add_exception_handler(InvalidSessionError, _handle_unauthorized)
    app.add_exception_handler(InvalidInviteCodeError, _handle_unauthorized)
    app.add_exception_handler(UsernameAlreadyTakenError, _handle_conflict)
    app.add_exception_handler(WeakPasswordError, _handle_invalid_input)
    app.add_exception_handler(InvalidGoogleTokenError, _handle_unauthorized)
    app.add_exception_handler(GoogleAccountEmailConflictError, _handle_conflict)
    app.add_exception_handler(GoogleSignInNotConfiguredError, _handle_service_unavailable)
    app.add_exception_handler(UploadTooLargeError, _handle_payload_too_large)
    app.add_exception_handler(RateLimitExceeded, _handle_rate_limit_exceeded)
    app.add_exception_handler(ProviderConfigurationError, _handle_provider_unavailable)
    app.add_exception_handler(ProviderRequestError, _handle_provider_request_failure)
    app.add_exception_handler(OSError, _handle_storage_failure)
    app.add_exception_handler(ScholarOSError, _handle_domain_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
