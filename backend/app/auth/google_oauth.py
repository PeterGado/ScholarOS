from typing import Any

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token


def verify_google_id_token(raw_id_token: str, *, client_id: str) -> dict[str, Any]:
    """Verifies a Google Identity Services ID token's signature, expiry, and audience against
    Google's own public certs (network call, cached by the underlying library across calls).
    Raises ValueError (google-auth's own contract) for any invalid token - callers translate
    that to InvalidGoogleTokenError, never inspecting or logging the raw token itself.

    Injected into GoogleSignInUseCase as a callable rather than called directly there, so tests
    supply a fake instead of hitting Google's real network for cert fetching.
    """
    return google_id_token.verify_oauth2_token(raw_id_token, google_requests.Request(), audience=client_id)
