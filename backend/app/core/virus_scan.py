import hashlib
import logging

import httpx

logger = logging.getLogger(__name__)

__all__ = ["is_known_malicious"]

_LOOKUP_URL = "https://www.virustotal.com/api/v3/files/{sha256}"
_REQUEST_TIMEOUT_SECONDS = 5.0
# At least this many independent engines flagging the file, not just one - a single AV engine
# false-positive is common and not worth rejecting a legitimate academic document over.
_MALICIOUS_THRESHOLD = 2


def is_known_malicious(content: bytes, *, api_key: str, client: httpx.Client | None = None) -> bool:
    """Checks the uploaded content's SHA-256 hash against VirusTotal's existing analysis
    database (2026-10-11, production-readiness pass). Only the hash ever leaves this process -
    never the file content itself - a deliberate scope choice over uploading the actual file for
    a fresh scan: VirusTotal's own file-upload-and-analyze flow is asynchronous (minutes, not
    seconds) and doesn't fit a synchronous upload request, and sending real (possibly sensitive)
    research document content to a third party is a real privacy cost this project isn't willing
    to pay for this control. This catches already-known malware by hash; it will not catch a
    brand-new, never-before-seen malicious file - a stated, deliberate limitation, not an
    oversight. Complements, not replaces, the existing format/size checks
    (app.core.document_formats, app.core.uploads).

    Fails open (returns False, i.e. "not known malicious") on a hash VirusTotal has never seen
    (404 - the overwhelmingly common case for legitimate novel documents), and on any network or
    API failure - this is a defense-in-depth layer on top of the already-sufficient format/size
    checks, not the sole control, so an outage must never block every document upload. Returns
    True (block) only on an explicit, multi-engine malicious verdict already on file.
    """
    sha256 = hashlib.sha256(content).hexdigest()

    owns_client = client is None
    http_client = client or httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS)
    try:
        response = http_client.get(_LOOKUP_URL.format(sha256=sha256), headers={"x-apikey": api_key})
        if response.status_code == 404:
            return False
        if response.status_code != 200:
            logger.warning("VirusTotal lookup returned status %s; treating as not malicious.", response.status_code)
            return False
        stats = response.json()["data"]["attributes"]["last_analysis_stats"]
        malicious_count = stats.get("malicious", 0) + stats.get("suspicious", 0)
        return malicious_count >= _MALICIOUS_THRESHOLD
    except httpx.HTTPError as exc:
        logger.warning("VirusTotal lookup request failed (%s); treating as not malicious.", exc)
        return False
    except (ValueError, KeyError):
        logger.warning("VirusTotal lookup returned an unexpected response shape; treating as not malicious.")
        return False
    finally:
        if owns_client:
            http_client.close()
