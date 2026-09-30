import httpx
import pytest

from app.ai import wikipedia as wikipedia_module
from app.ai.wikipedia import fetch_wikipedia_background


@pytest.fixture(autouse=True)
def _clear_cache():
    """The module keeps a process-lifetime cache keyed by topic - clear it before and after
    every test so tests never see another test's cached result for the same topic string.
    """
    wikipedia_module._cache.clear()
    yield
    wikipedia_module._cache.clear()


def _client_for(opensearch_response, summary_response=None, *, summary_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if "opensearch" in str(request.url):
            return httpx.Response(200, json=opensearch_response)
        return httpx.Response(summary_status, json=summary_response or {})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_returns_a_formatted_summary_for_a_resolved_topic():
    client = _client_for(
        ["Coastal erosion", ["Coastal erosion"], [], []],
        {"title": "Coastal erosion", "extract": "The wearing away of land along a shoreline."},
    )

    result = fetch_wikipedia_background("coastal erosion", client=client)

    assert result == "Coastal erosion: The wearing away of land along a shoreline."


def test_returns_none_when_no_matching_article_is_found():
    client = _client_for(["nonsense topic", [], [], []])

    result = fetch_wikipedia_background("nonsense topic", client=client)

    assert result is None


def test_returns_none_when_the_summary_has_no_extract():
    client = _client_for(
        ["Topic", ["Topic"], [], []],
        {"title": "Topic", "extract": ""},
    )

    result = fetch_wikipedia_background("Topic", client=client)

    assert result is None


def test_returns_none_and_never_raises_on_a_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = fetch_wikipedia_background("Topic", client=client)

    assert result is None


def test_returns_none_and_never_raises_on_an_http_error_status():
    client = _client_for(["Topic", ["Topic"], [], []], summary_status=500)

    result = fetch_wikipedia_background("Topic", client=client)

    assert result is None


def test_blank_topic_returns_none_without_making_a_request():
    client = _client_for(["", [], [], []])

    result = fetch_wikipedia_background("   ", client=client)

    assert result is None


def test_a_long_extract_is_truncated():
    long_extract = "Sentence one. " * 200
    client = _client_for(
        ["Topic", ["Topic"], [], []],
        {"title": "Topic", "extract": long_extract},
    )

    result = fetch_wikipedia_background("Topic", client=client)

    assert result is not None
    assert len(result) <= wikipedia_module._MAX_SUMMARY_LENGTH + len("Topic: ") + 1
    assert result.endswith(".")


def test_a_successful_fetch_is_cached_so_a_second_call_makes_no_request():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if "opensearch" in str(request.url):
            return httpx.Response(200, json=["Topic", ["Topic"], [], []])
        return httpx.Response(200, json={"title": "Topic", "extract": "A summary."})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    first = fetch_wikipedia_background("Topic", client=client)
    requests_after_first = call_count["n"]
    second = fetch_wikipedia_background("Topic", client=client)

    assert first == second == "Topic: A summary."
    assert call_count["n"] == requests_after_first  # no new request on the second call


def test_a_failed_fetch_is_not_cached_so_a_later_call_retries():
    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    failing_client = httpx.Client(transport=httpx.MockTransport(failing_handler))
    assert fetch_wikipedia_background("Topic", client=failing_client) is None

    working_client = _client_for(
        ["Topic", ["Topic"], [], []],
        {"title": "Topic", "extract": "A summary."},
    )
    assert fetch_wikipedia_background("Topic", client=working_client) == "Topic: A summary."
