import httpx

from app.auth.bot_protection import verify_turnstile_token


def _client_for(status: int, body: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_successful_verification_returns_true():
    client = _client_for(200, {"success": True})

    assert verify_turnstile_token("real-token", secret_key="secret", client=client) is True


def test_an_unsuccessful_verification_returns_false():
    client = _client_for(200, {"success": False, "error-codes": ["invalid-input-response"]})

    assert verify_turnstile_token("bad-token", secret_key="secret", client=client) is False


def test_a_non_200_response_fails_closed():
    client = _client_for(500, {})

    assert verify_turnstile_token("real-token", secret_key="secret", client=client) is False


def test_a_malformed_json_response_fails_closed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    assert verify_turnstile_token("real-token", secret_key="secret", client=client) is False


def test_a_network_error_fails_closed():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    assert verify_turnstile_token("real-token", secret_key="secret", client=client) is False


def test_an_empty_token_fails_closed_without_a_network_call():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"success": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    assert verify_turnstile_token("", secret_key="secret", client=client) is False
    assert calls == []
