import httpx
import pytest

from app.email.exceptions import EmailSendError
from app.email.resend import send_email


def _client_for(status: int, body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body or {"id": "abc123"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sends_successfully_with_a_200_response():
    client = _client_for(200)

    send_email(
        to="person@example.com", subject="Hi", html="<p>hi</p>",
        api_key="re_test", from_address="ScholarOS <onboarding@resend.dev>", client=client,
    )  # must not raise


def test_raises_when_no_api_key_is_configured():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should never make a request with no API key")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(EmailSendError):
        send_email(
            to="person@example.com", subject="Hi", html="<p>hi</p>",
            api_key=None, from_address="ScholarOS <onboarding@resend.dev>", client=client,
        )


def test_raises_on_a_non_2xx_response():
    client = _client_for(401, {"message": "invalid key"})

    with pytest.raises(EmailSendError):
        send_email(
            to="person@example.com", subject="Hi", html="<p>hi</p>",
            api_key="re_bad", from_address="ScholarOS <onboarding@resend.dev>", client=client,
        )


def test_raises_on_a_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(EmailSendError):
        send_email(
            to="person@example.com", subject="Hi", html="<p>hi</p>",
            api_key="re_test", from_address="ScholarOS <onboarding@resend.dev>", client=client,
        )


def test_sends_the_request_with_the_expected_headers_and_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        captured["body"] = request.read()
        return httpx.Response(200, json={"id": "abc123"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    send_email(
        to="person@example.com", subject="Reset your password", html="<p>link</p>",
        api_key="re_test_key", from_address="ScholarOS <onboarding@resend.dev>", client=client,
    )

    assert captured["headers"]["Authorization"] == "Bearer re_test_key"
    assert b'"to":["person@example.com"]' in captured["body"]
    assert b'"subject":"Reset your password"' in captured["body"]
