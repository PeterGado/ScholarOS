import hashlib
import logging

import httpx

logger = logging.getLogger(__name__)

__all__ = ["is_breached_password"]

_RANGE_URL = "https://api.pwnedpasswords.com/range/{prefix}"
_REQUEST_TIMEOUT_SECONDS = 5.0


def is_breached_password(password: str, *, client: httpx.Client | None = None) -> bool:
    """Checks a password against HIBP's Pwned Passwords API via k-anonymity (2026-10-06,
    external security review - NIST 800-63B recommends checking new passwords against known
    breach corpora). Only the first 5 hex characters of the password's SHA-1 hash ever leave
    this process; the real password and the full hash never do.

    Fails open (returns False, i.e. "not known to be breached") on any network or API failure -
    this is a defense-in-depth enhancement on top of bcrypt (the actual security control), so an
    HIBP outage must never block registration or password reset.
    """
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]

    owns_client = client is None
    http_client = client or httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS)
    try:
        response = http_client.get(_RANGE_URL.format(prefix=prefix))
        if response.status_code != 200:
            logger.warning("Pwned Passwords API returned status %s; treating as not breached.", response.status_code)
            return False
        return any(line.split(":")[0] == suffix for line in response.text.splitlines())
    except httpx.HTTPError as exc:
        logger.warning("Pwned Passwords API request failed (%s); treating as not breached.", exc)
        return False
    finally:
        if owns_client:
            http_client.close()
