import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

__all__ = ["OpenAlexWork", "SourceSearchUnavailableError", "get_openalex_work_by_id", "search_openalex_works"]

_SEARCH_URL = "https://api.openalex.org/works"
_WORK_URL = "https://api.openalex.org/works/{work_id}"
_REQUEST_TIMEOUT_SECONDS = 10.0
_SELECT_FIELDS = "id,doi,title,publication_year,authorships,open_access,primary_location,abstract_inverted_index"
_MAX_RESULTS = 25


class SourceSearchUnavailableError(Exception):
    """Raised when a real call to OpenAlex fails - a network error, a non-200 response, or a
    malformed response body (2026-10-17, search-and-import source discovery). Deliberately
    distinct from a normal, successful empty result list ("nothing found"): unlike the
    fire-and-forget background-enrichment integrations elsewhere in this codebase (Wikipedia,
    the web-source chat-grounding fetch), this is a user-initiated search action the caller is
    actively waiting on - the caller needs to tell "the search didn't run" apart from "it ran
    and found nothing" to show the right message, so this raises instead of failing open.
    """


@dataclass(frozen=True)
class OpenAlexWork:
    """One candidate source from an OpenAlex search or single-work lookup. `fetchable_url` is
    the best available legal full-text link (a direct PDF when OpenAlex has one, otherwise the
    open-access landing page) - `None` when OpenAlex has no open-access location for this work
    at all, which is common (most of the scholarly record is still paywalled). `abstract` is
    reconstructed from OpenAlex's inverted-index format (see `_reconstruct_abstract`) - OpenAlex
    cannot legally serve a plain abstract string directly, only the positions each word occupies.
    """

    openalex_id: str
    doi: str | None
    title: str
    authors: tuple[str, ...]
    publication_year: int | None
    source_name: str | None
    is_open_access: bool
    fetchable_url: str | None
    abstract: str | None


def _reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    """OpenAlex abstracts arrive as {word: [positions]} rather than plain text, for copyright
    reasons (the inverted index itself is legally republishable; the original prose is not,
    depending on the publisher). This is the standard, documented reconstruction: place each
    word at every position it occupies, then join in order.
    """
    if not inverted_index:
        return None
    max_position = max((pos for positions in inverted_index.values() for pos in positions), default=-1)
    if max_position < 0:
        return None
    words: list[str] = [""] * (max_position + 1)
    for word, positions in inverted_index.items():
        for pos in positions:
            if 0 <= pos <= max_position:
                words[pos] = word
    text = " ".join(w for w in words if w)
    return text or None


def _parse_work(raw: dict) -> OpenAlexWork:
    openalex_id = raw.get("id") or ""
    doi = raw.get("doi")
    if doi and doi.startswith("https://doi.org/"):
        doi = doi.removeprefix("https://doi.org/")
    title = (raw.get("title") or "").strip() or "Untitled"
    authors = tuple(
        name
        for authorship in (raw.get("authorships") or [])
        if (name := (authorship.get("author") or {}).get("display_name"))
    )
    publication_year = raw.get("publication_year")
    primary_location = raw.get("primary_location") or {}
    source_name = (primary_location.get("source") or {}).get("display_name")
    open_access = raw.get("open_access") or {}
    is_open_access = bool(open_access.get("is_oa"))
    fetchable_url = primary_location.get("pdf_url") or open_access.get("oa_url")
    abstract = _reconstruct_abstract(raw.get("abstract_inverted_index"))
    return OpenAlexWork(
        openalex_id=openalex_id,
        doi=doi,
        title=title,
        authors=authors,
        publication_year=publication_year,
        source_name=source_name,
        is_open_access=is_open_access,
        fetchable_url=fetchable_url,
        abstract=abstract,
    )


def search_openalex_works(
    query: str, *, api_key: str, limit: int = 10, client: httpx.Client | None = None
) -> list[OpenAlexWork]:
    """Searches OpenAlex's ~250M-work open scholarly index (2026-10-17, NotebookLM-style
    search-and-import source discovery - a curated, user-approved list of specific results, not
    an unrestricted crawl of the open web). `api_key` is required: OpenAlex's unauthenticated
    tier shares a tiny budget across every caller on the same network IP, not viable for a real
    feature (see `app.core.config.openalex_api_key`'s own docstring).

    Raises `SourceSearchUnavailableError` on any network error, non-200 response, or malformed
    body - see that exception's own docstring for why this doesn't fail open like this
    codebase's other external integrations.
    """
    owns_client = client is None
    http_client = client or httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS)
    try:
        response = http_client.get(
            _SEARCH_URL,
            params={
                "search": query,
                "per_page": max(1, min(limit, _MAX_RESULTS)),
                "select": _SELECT_FIELDS,
                "api_key": api_key,
            },
        )
        if response.status_code != 200:
            raise SourceSearchUnavailableError(f"OpenAlex search returned status {response.status_code}")
        body = response.json()
        return [_parse_work(raw) for raw in body.get("results", [])]
    except httpx.HTTPError as exc:
        logger.warning("OpenAlex search request failed: %s", exc)
        raise SourceSearchUnavailableError(str(exc)) from exc
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        logger.warning("OpenAlex search returned an unexpected response shape: %s", exc)
        raise SourceSearchUnavailableError("OpenAlex returned an unexpected response.") from exc
    finally:
        if owns_client:
            http_client.close()


def get_openalex_work_by_id(
    openalex_id: str, *, api_key: str, client: httpx.Client | None = None
) -> OpenAlexWork | None:
    """Re-fetches a single work by its OpenAlex ID server-side at import time (2026-10-17) -
    never trusts client-supplied title/author/year/DOI for a document the import endpoint is
    about to create; only the ID travels from the search results the client saw back to the
    import request, and everything else is re-resolved from OpenAlex directly here.

    Returns `None` (not an exception) for a 404 - a genuinely missing/withdrawn work is a normal
    outcome for this lookup, unlike a search failing to run at all. Still raises
    `SourceSearchUnavailableError` for a real failure (network error, non-404 non-200, malformed
    body), same reasoning as `search_openalex_works`.
    """
    work_id = openalex_id.rsplit("/", 1)[-1]  # accepts either the bare ID or the full openalex.org URL
    owns_client = client is None
    http_client = client or httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS)
    try:
        response = http_client.get(_WORK_URL.format(work_id=work_id), params={"select": _SELECT_FIELDS, "api_key": api_key})
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise SourceSearchUnavailableError(f"OpenAlex work lookup returned status {response.status_code}")
        return _parse_work(response.json())
    except httpx.HTTPError as exc:
        logger.warning("OpenAlex work lookup request failed: %s", exc)
        raise SourceSearchUnavailableError(str(exc)) from exc
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        logger.warning("OpenAlex work lookup returned an unexpected response shape: %s", exc)
        raise SourceSearchUnavailableError("OpenAlex returned an unexpected response.") from exc
    finally:
        if owns_client:
            http_client.close()
