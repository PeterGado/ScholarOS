from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.exceptions import InvalidSessionError

_bearer_scheme = HTTPBearer(auto_error=False)


def extract_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Extracts the raw token from `Authorization: Bearer <token>`. A missing header, a
    non-Bearer scheme, and a malformed header are all treated the same as an unknown or
    ended token - one InvalidSessionError, one 401, for every way of not presenting a valid
    session. No separate status per variant; documented here rather than scattered.

    Shared by app.auth.routes (logout) and core.dependencies (get_current_user_id) - Stage 6
    lifts this out of app.auth.routes so both call sites compose the same extraction
    dependency instead of duplicating it (ADR-010 Compliance Rules: session verification
    logic lives only in the app.auth boundary, never duplicated).
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidSessionError()
    return credentials.credentials
