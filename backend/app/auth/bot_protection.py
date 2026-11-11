import logging

import httpx

logger = logging.getLogger(__name__)

__all__ = ["verify_turnstile_token"]

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_REQUEST_TIMEOUT_SECONDS = 5.0


def verify_turnstile_token(
    token: str, *, secret_key: str, remote_ip: str | None = None, client: httpx.Client | None = None
) -> bool:
    """Verifies a Cloudflare Turnstile token against Cloudflare's own siteverify endpoint
    (2026-10-11, production-readiness pass - bot protection on registration). Returns True only
    on an explicit `success: true` from Cloudflare.

    Fails closed (returns False) on a missing/empty token, a non-200 response, a malformed
    response body, or a network error - unlike `is_breached_password`'s fail-open design, this
    *is* the actual security control being added here (not a defense-in-depth layer on top of
    an already-sufficient one), so a Cloudflare outage blocking registration is the safer
    failure mode than silently letting every registration through unchecked during that outage.
    Registration can be retried once Cloudflare recovers; an unnoticed bot-registration flood
    during an outage cannot be undone as easily.
    """
    if not token:
        return False

    owns_client = client is None
    http_client = client or httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS)
    try:
        payload = {"secret": secret_key, "response": token}
        if remote_ip:
            payload["remoteip"] = remote_ip
        response = http_client.post(_VERIFY_URL, data=payload)
        if response.status_code != 200:
            logger.warning("Turnstile siteverify returned status %s; treating as failed.", response.status_code)
            return False
        body = response.json()
        return bool(body.get("success") is True)
    except httpx.HTTPError as exc:
        logger.warning("Turnstile siteverify request failed (%s); treating as failed.", exc)
        return False
    except ValueError:
        logger.warning("Turnstile siteverify returned a non-JSON response; treating as failed.")
        return False
    finally:
        if owns_client:
            http_client.close()
