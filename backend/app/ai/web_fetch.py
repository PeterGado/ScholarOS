import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from scrapling import Fetcher

logger = logging.getLogger(__name__)
# scrapling logs an INFO line per fetch by default (status, URL, a spoofed referer) - useful
# during manual testing, pure noise in production logs otherwise; this app's own logging stays
# operational-facts-only (see app.core.middleware, app.auth.service's own logging discipline).
logging.getLogger("scrapling").setLevel(logging.WARNING)

__all__ = ["WebSource", "extract_urls", "fetch_web_source"]

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")
_MAX_URLS_PER_MESSAGE = 3
_MAX_CONTENT_LENGTH = 3000
_REQUEST_TIMEOUT_SECONDS = 8
_USER_AGENT = "ScholarOS/1.0 (personal research-writing assistant; fetches a URL only when a user pastes one in chat)"


@dataclass(frozen=True)
class WebSource:
    url: str
    content: str


def extract_urls(text: str) -> list[str]:
    """Pulls up to `_MAX_URLS_PER_MESSAGE` distinct http(s) URLs out of a chat message, in the
    order they appear (2026-10-17, web-source grounding). Trailing punctuation a sentence would
    naturally attach to a URL (a closing paren, a comma, a period) is stripped so "see
    https://example.com." doesn't fetch a URL with a trailing dot. Deliberately capped per
    message - this is a best-effort grounding aid, not a bulk crawler, and each URL costs a real
    network round trip inside the same Work Item that generates the reply.
    """
    seen: list[str] = []
    for match in _URL_PATTERN.finditer(text):
        url = match.group(0).rstrip(").,;:!?”'\"")
        if url and url not in seen:
            seen.append(url)
        if len(seen) >= _MAX_URLS_PER_MESSAGE:
            break
    return seen


def _is_safe_public_host(hostname: str) -> bool:
    """Resolves `hostname` and rejects it if any resolved address is private, loopback,
    link-local, multicast, reserved, or unspecified (2026-10-17, SSRF defense) - blocks the
    overwhelming majority of real-world SSRF targets (localhost, 127.0.0.1, 169.254.169.254
    cloud metadata endpoints, RFC1918 internal ranges, etc.).

    Known, accepted residual gap: this checks DNS *before* the fetch, not at connection time -
    no DNS-pinning hook is exposed by this app's HTTP stack (curl_cffi, via scrapling) without
    reaching into lower-level curl options, which would be a much larger change than this
    feature warrants. A sufficiently sophisticated DNS-rebinding attack (resolving safely at
    check-time, then to an internal address at connect-time, typically requiring a very short
    DNS TTL and precise timing) is not defended against. Accepted given the threat model here -
    this is reachable only by an authenticated, rate-limited user, not anonymous public input -
    rather than building full IP-pinning for this feature.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, UnicodeError):
        return False

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return bool(infos)


def _is_safe_to_fetch(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False
    return _is_safe_public_host(parsed.hostname)


def fetch_web_source(url: str) -> WebSource | None:
    """Best-effort fetch-and-extract for a URL a user pasted into a chat message (2026-10-17,
    web-source grounding - "paste a URL and have it fetched into the same knowledge pipeline").
    Uses scrapling's basic `Fetcher` (curl_cffi-backed HTTP, not a full browser) - deliberately
    not `StealthyFetcher`/`DynamicFetcher`, which need real browser binaries; most pasted URLs
    (articles, papers, blog posts) render their content without JavaScript, and this app already
    avoids adding heavy runtime dependencies where a lighter one suffices (ADR-005's own
    MVP-scale philosophy, the Postgres-over-Redis rate-limiter precedent).

    SSRF-checked before fetching (see `_is_safe_to_fetch`/`_is_safe_public_host`), fetched with
    `follow_redirects=False` (a redirect is never silently followed to an unvalidated target),
    `retries=0` (this is optional, best-effort enrichment inside an already-running background
    Work Item - failing fast beats scrapling's own default 3-attempt retry-with-delay), and the
    extracted text is capped at `_MAX_CONTENT_LENGTH` characters before being handed to the
    caller, bounding both the prompt-budget cost and (loosely) the memory cost of a very large
    page - not a hard byte-level cap on the underlying fetch itself, since no such cap is exposed
    by this app's HTTP stack; the timeout is the real bound against a slow/huge response.

    Never raises: mirrors `app.ai.wikipedia.fetch_wikipedia_background` and
    `app.ai.crossref.fetch_crossref_work`'s own "never raise" contract - a blocked, unreachable,
    or malformed URL just means no web-source section is added to the prompt. Nothing here can
    break a chat reply.
    """
    if not _is_safe_to_fetch(url):
        return None

    try:
        response = Fetcher.get(
            url,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
            retries=0,
            headers={"User-Agent": _USER_AGENT},
        )
        if response.status != 200:
            return None

        text = (response.get_all_text() or "").strip()
        if not text:
            return None
        if len(text) > _MAX_CONTENT_LENGTH:
            truncated = text[:_MAX_CONTENT_LENGTH].rsplit(" ", 1)[0]
            text = (truncated or text[:_MAX_CONTENT_LENGTH]) + "..."

        return WebSource(url=url, content=text)
    except Exception:  # noqa: BLE001 - this function's whole contract is "never raise"
        logger.warning("Failed to fetch web source %s", url)
        return None
