import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

__all__ = ["WebSearchResult", "WebSearchUnavailableError", "search_web"]

_SEARCH_URL = "https://api.tavily.com/search"
_REQUEST_TIMEOUT_SECONDS = 10.0
_MAX_RESULTS = 20


class WebSearchUnavailableError(Exception):
    """Raised when a real call to Tavily fails - a network error, a non-200 response, or a
    malformed response body (2026-10-17, general web search discovery, mirrors
    app.ai.openalex.SourceSearchUnavailableError's own reasoning exactly). This is a
    user-initiated search action the caller is actively waiting on, so it raises instead of
    failing open like this codebase's background/fire-and-forget integrations.
    """


@dataclass(frozen=True)
class WebSearchResult:
    """One candidate page from a Tavily web search - a result the user may choose to import,
    not yet a Research Document. Unlike OpenAlexWork, there is no authoritative registry to
    re-resolve this by ID at import time: `url` and `title` travel back from the search result
    the client saw exactly as shown, the same trust boundary the existing chat-paste-URL feature
    already accepts for any URL a user provides. The real security boundary stays fetch-time SSRF
    checking (app.ai.web_fetch.fetch_web_source), not a server-side re-lookup.
    """

    url: str
    title: str
    snippet: str | None


def _parse_result(raw: dict) -> WebSearchResult:
    url = raw.get("url") or ""
    title = (raw.get("title") or "").strip() or url
    snippet = (raw.get("content") or "").strip() or None
    return WebSearchResult(url=url, title=title, snippet=snippet)


def search_web(
    query: str, *, api_key: str, limit: int = 10, client: httpx.Client | None = None
) -> list[WebSearchResult]:
    """Searches the open web via Tavily (2026-10-17, NotebookLM-style "Discover sources" applied
    beyond the scholarly index - a curated, user-approved list of specific results, not an
    unrestricted crawl). `api_key` is required: Tavily has no viable unauthenticated tier.

    Raises `WebSearchUnavailableError` on any network error, non-200 response, or malformed
    body - see that exception's own docstring for why this doesn't fail open.
    """
    owns_client = client is None
    http_client = client or httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS)
    try:
        response = http_client.post(
            _SEARCH_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"query": query, "max_results": max(1, min(limit, _MAX_RESULTS))},
        )
        if response.status_code != 200:
            raise WebSearchUnavailableError(f"Tavily search returned status {response.status_code}")
        body = response.json()
        return [_parse_result(raw) for raw in body.get("results", [])]
    except httpx.HTTPError as exc:
        logger.warning("Tavily search request failed: %s", exc)
        raise WebSearchUnavailableError(str(exc)) from exc
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        logger.warning("Tavily search returned an unexpected response shape: %s", exc)
        raise WebSearchUnavailableError("Tavily returned an unexpected response.") from exc
    finally:
        if owns_client:
            http_client.close()
