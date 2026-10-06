from dataclasses import dataclass
from urllib.parse import quote

import httpx

__all__ = ["CrossrefWork", "fetch_crossref_work"]

_WORK_URL = "https://api.crossref.org/works/{doi}"
_REQUEST_TIMEOUT_SECONDS = 5.0
_USER_AGENT = "ScholarOS/1.0 (mailto:ohiomahim@gmail.com)"
"""Crossref's own etiquette policy (https://api.crossref.org/) asks for a mailto in the
User-Agent to get routed to its faster "polite pool" - this is the project's own contact
address, not a per-request user value."""


@dataclass(frozen=True)
class CrossrefWork:
    title: str
    authors: tuple[str, ...]
    year: int | None


def fetch_crossref_work(doi: str, *, client: httpx.Client | None = None) -> CrossrefWork | None:
    """Looks up a DOI against Crossref's free, public, no-auth-required works API
    (2026-10-06, citation grounding) - confirms a user-supplied DOI resolves to a real work
    before VerifyDocumentDoiUseCase trusts it, rather than taking typed-in metadata on faith.

    Never raises: a malformed DOI, an unknown DOI (404), a network error, or a timeout all
    just mean "can't verify this one" - the caller treats that as DoiVerificationStatus.NOT_FOUND,
    not a reason to fail document processing (same never-raises contract as
    fetch_wikipedia_background, and the same reasoning: this is enrichment, not a dependency
    anything else needs to succeed).
    """
    normalized = doi.strip()
    if not normalized:
        return None

    owns_client = client is None
    http_client = client or httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": _USER_AGENT})
    try:
        response = http_client.get(_WORK_URL.format(doi=quote(normalized, safe="")))
        response.raise_for_status()
        message = response.json().get("message", {})

        titles = message.get("title") or []
        title = titles[0] if titles else normalized

        authors = tuple(
            family for author in message.get("author", []) if (family := author.get("family"))
        )

        year = _extract_year(message)

        return CrossrefWork(title=title, authors=authors, year=year)
    except Exception:  # noqa: BLE001 - this function's whole contract is "never raise"
        return None
    finally:
        if owns_client:
            http_client.close()


def _extract_year(message: dict) -> int | None:
    """Crossref has no single reliable "the" publication date field - a work can carry
    published-print, published-online, published, or only `created`, and this prefers them in
    that order (print/online beat the record's creation date as the real publication year).
    """
    for key in ("published-print", "published-online", "published", "created"):
        date_parts = message.get(key, {}).get("date-parts")
        if date_parts and date_parts[0] and date_parts[0][0]:
            return int(date_parts[0][0])
    return None
