import httpx

from app.email.exceptions import EmailSendError

__all__ = ["send_email"]

_SEND_URL = "https://api.resend.com/emails"
_REQUEST_TIMEOUT_SECONDS = 10.0


def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    api_key: str | None,
    from_address: str,
    client: httpx.Client | None = None,
) -> None:
    """Sends a single transactional email via Resend's API (2026-10-06, password reset - the
    first feature in this codebase that sends real email).

    Deliberately raises on any failure rather than the "never raises, return None" contract
    app.ai.wikipedia/app.ai.crossref use - those are optional prompt enrichment; a password
    reset email *is* the deliverable, so a caller must know when it didn't go out rather than
    silently proceeding as if it did. `api_key is None` (RESEND_API_KEY unset) raises the same
    EmailSendError as a real provider failure, matching ProviderConfigurationError's existing
    "missing config fails the same way a bad call would" precedent in app.ai.exceptions.

    `from_address` is passed in, not hardcoded or read from Settings here - until a custom
    domain is verified with Resend, this must be their shared `onboarding@resend.dev` sender;
    the caller (not this low-level client) is the right place to decide which.
    """
    if not api_key:
        raise EmailSendError("Email sending is not configured.")

    owns_client = client is None
    http_client = client or httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS)
    try:
        response = http_client.post(
            _SEND_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"from": from_address, "to": [to], "subject": subject, "html": html},
        )
        if response.status_code >= 400:
            # Never echo the raw response body back into logs/exceptions here - Resend's error
            # payloads can include the request's own `to` address, which is fine, but a 401
            # response gives no reason to risk ever including the Authorization header's value.
            raise EmailSendError(f"Resend API request failed with status {response.status_code}.")
    except httpx.HTTPError as exc:
        raise EmailSendError(f"Network error sending email: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()
