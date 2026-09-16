from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_allowed_origin_receives_cors_headers():
    """A browser-based frontend on a different origin (the Vite dev server) cannot reach this
    API at all without CORS headers - found as a real defect during the Frontend milestone's
    first genuine browser-based (not TestClient/curl) request. Not a design choice: every
    cross-origin browser request is blocked by the browser itself unless the server opts in.
    """
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_disallowed_origin_receives_no_cors_headers():
    response = client.get("/health", headers={"Origin": "http://evil.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
