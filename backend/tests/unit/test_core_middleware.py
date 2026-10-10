from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.middleware import MaxBodySizeMiddleware


async def _echo(request):
    body = await request.body()
    return PlainTextResponse(f"received {len(body)} bytes")


def _build_client(max_bytes: int) -> TestClient:
    app = Starlette(routes=[Route("/", _echo, methods=["POST"])])
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=max_bytes)
    return TestClient(app)


def test_a_request_within_the_limit_reaches_the_route():
    client = _build_client(max_bytes=1000)
    response = client.post("/", content=b"x" * 500)
    assert response.status_code == 200
    assert response.text == "received 500 bytes"


def test_a_request_exceeding_the_limit_is_rejected_before_the_route():
    client = _build_client(max_bytes=1000)
    response = client.post("/", content=b"x" * 2000)
    assert response.status_code == 413
    assert response.json()["error_type"] == "RequestBodyTooLargeError"


def test_a_request_exactly_at_the_limit_is_accepted():
    client = _build_client(max_bytes=1000)
    response = client.post("/", content=b"x" * 1000)
    assert response.status_code == 200


def test_a_request_with_no_body_is_unaffected():
    client = _build_client(max_bytes=1000)
    response = client.post("/", content=b"")
    assert response.status_code == 200
