def test_security_headers_are_present_on_a_normal_response(client):
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_security_headers_are_present_on_an_error_response(client):
    """The headers must not be conditional on a 2xx response - an attacker probing for
    weaknesses is exactly who should see them."""
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"})

    assert response.status_code == 401
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
