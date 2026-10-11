import httpx

from app.core.virus_scan import is_known_malicious


def _client_for(status: int, body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if body is None:
            return httpx.Response(status)
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_an_unknown_hash_is_not_treated_as_malicious():
    client = _client_for(404)

    assert is_known_malicious(b"some harmless document content", api_key="key", client=client) is False


def test_a_hash_with_no_malicious_verdicts_is_safe():
    client = _client_for(200, {"data": {"attributes": {"last_analysis_stats": {"malicious": 0, "suspicious": 0}}}})

    assert is_known_malicious(b"content", api_key="key", client=client) is False


def test_a_single_engine_flag_is_not_enough_to_block():
    client = _client_for(200, {"data": {"attributes": {"last_analysis_stats": {"malicious": 1, "suspicious": 0}}}})

    assert is_known_malicious(b"content", api_key="key", client=client) is False


def test_multiple_engine_flags_are_blocked():
    client = _client_for(200, {"data": {"attributes": {"last_analysis_stats": {"malicious": 5, "suspicious": 1}}}})

    assert is_known_malicious(b"content", api_key="key", client=client) is True


def test_a_non_200_non_404_response_fails_open():
    client = _client_for(500)

    assert is_known_malicious(b"content", api_key="key", client=client) is False


def test_an_unexpected_response_shape_fails_open():
    client = _client_for(200, {"data": {}})

    assert is_known_malicious(b"content", api_key="key", client=client) is False


def test_a_network_error_fails_open():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    assert is_known_malicious(b"content", api_key="key", client=client) is False


def test_the_hash_is_computed_from_content_not_sent_as_content():
    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    is_known_malicious(b"some private research content", api_key="key", client=client)

    assert len(captured_requests) == 1
    assert b"some private research content" not in captured_requests[0].url.raw_path
    # A SHA-256 hex digest is 64 chars - confirms the URL carries a hash, not the raw content.
    assert captured_requests[0].url.path.rsplit("/", 1)[-1].__len__() == 64
