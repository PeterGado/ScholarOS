import threading
from urllib.parse import quote

import httpx

__all__ = ["fetch_wikipedia_background"]

_OPENSEARCH_URL = "https://en.wikipedia.org/w/api.php"
_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_REQUEST_TIMEOUT_SECONDS = 5.0
_MAX_SUMMARY_LENGTH = 1500
_USER_AGENT = "ScholarOS/1.0 (personal research-writing assistant)"

_cache: dict[str, str] = {}
_cache_lock = threading.Lock()


def fetch_wikipedia_background(topic: str, *, client: httpx.Client | None = None) -> str | None:
    """Best-effort general background knowledge for a project's topic, drawn from Wikipedia
    (2026-09-30, explicitly requested as part of a project's background knowledge - "AI
    knowledge + wikipedia knowledge" - combined with the model's own inherent knowledge at
    generation time, not supplied as per-message citable evidence; see BACKGROUND KNOWLEDGE
    (WIKIPEDIA) in context_assembly.py for how it's kept clearly separate from the user's own
    uploaded RESEARCH EVIDENCE).

    Cached per topic for the life of this process once a fetch succeeds - a project's topic
    rarely changes, so this costs one real network call per topic, not one per chat message.
    Failures are deliberately not cached, so a transient outage doesn't permanently blank out a
    topic's background for the rest of the process's life.

    Never raises: a network error, timeout, or no matching Wikipedia article all just mean no
    background section is added to the prompt. Nothing here can break a chat reply - this is
    genuinely optional context, not a dependency the generation flow needs to succeed.
    """
    normalized = topic.strip()
    if not normalized:
        return None

    with _cache_lock:
        cached = _cache.get(normalized)
    if cached is not None:
        return cached

    owns_client = client is None
    http_client = client or httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": _USER_AGENT})
    try:
        summary = _fetch_summary(normalized, http_client)
    finally:
        if owns_client:
            http_client.close()

    if summary:
        with _cache_lock:
            _cache[normalized] = summary
    return summary


def _fetch_summary(topic: str, client: httpx.Client) -> str | None:
    try:
        title = _resolve_title(topic, client)
        if not title:
            return None

        response = client.get(_SUMMARY_URL.format(title=quote(title, safe="")))
        response.raise_for_status()
        data = response.json()

        extract = (data.get("extract") or "").strip()
        if not extract:
            return None
        if len(extract) > _MAX_SUMMARY_LENGTH:
            truncated = extract[:_MAX_SUMMARY_LENGTH].rsplit(". ", 1)[0]
            extract = (truncated or extract[:_MAX_SUMMARY_LENGTH]) + "."

        page_title = data.get("title") or title
        return f"{page_title}: {extract}"
    except Exception:  # noqa: BLE001 - this function's whole contract is "never raise"
        return None


def _resolve_title(topic: str, client: httpx.Client) -> str | None:
    response = client.get(
        _OPENSEARCH_URL,
        params={"action": "opensearch", "search": topic, "limit": 1, "namespace": 0, "format": "json"},
    )
    response.raise_for_status()
    data = response.json()
    titles = data[1] if isinstance(data, list) and len(data) > 1 else []
    return titles[0] if titles else None
