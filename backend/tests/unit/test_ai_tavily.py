import httpx
import pytest

from app.ai.tavily import WebSearchUnavailableError, search_web

_RAW_RESULT = {
    "url": "https://example.com/paper",
    "title": "A Real Page Title",
    "content": "A real snippet of page content.",
    "score": 0.49,
    "raw_content": None,
    "id": "abc-00",
}


def _client_for(status: int, body: dict | list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if body is None:
            return httpx.Response(status)
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_search_parses_a_real_shaped_result():
    client = _client_for(200, {"results": [_RAW_RESULT], "query": "q", "response_time": 1.0})

    results = search_web("query", api_key="key", client=client)

    assert len(results) == 1
    result = results[0]
    assert result.url == "https://example.com/paper"
    assert result.title == "A Real Page Title"
    assert result.snippet == "A real snippet of page content."


def test_search_falls_back_to_url_when_no_title():
    raw = dict(_RAW_RESULT)
    raw["title"] = ""
    client = _client_for(200, {"results": [raw]})

    results = search_web("query", api_key="key", client=client)

    assert results[0].title == "https://example.com/paper"


def test_search_handles_no_snippet():
    raw = dict(_RAW_RESULT)
    raw["content"] = ""
    client = _client_for(200, {"results": [raw]})

    results = search_web("query", api_key="key", client=client)

    assert results[0].snippet is None


def test_search_returns_empty_list_for_zero_results():
    client = _client_for(200, {"results": []})

    results = search_web("query", api_key="key", client=client)

    assert results == []


def test_search_sends_bearer_auth_header():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json={"results": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    search_web("my query", api_key="secret-key", limit=5, client=client)

    assert captured["authorization"] == "Bearer secret-key"


def test_search_caps_limit_at_twenty():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["max_results"] = json.loads(request.content)["max_results"]
        return httpx.Response(200, json={"results": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    search_web("query", api_key="key", limit=999, client=client)

    assert captured["max_results"] == 20


def test_search_raises_on_non_200_status():
    client = _client_for(401, {"detail": {"error": "Unauthorized: missing or invalid API key."}})

    with pytest.raises(WebSearchUnavailableError):
        search_web("query", api_key="bad-key", client=client)


def test_search_raises_on_a_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(WebSearchUnavailableError):
        search_web("query", api_key="key", client=client)


def test_search_raises_on_a_malformed_response_body():
    client = _client_for(200, ["not", "a", "dict"])

    with pytest.raises(WebSearchUnavailableError):
        search_web("query", api_key="key", client=client)
