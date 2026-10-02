def _create_workspace(client, headers) -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Coastal erosion"}, headers=headers)
    return response.json()


def test_list_segment_templates_includes_the_fyp1_guide(client, auth_headers):
    response = client.get("/writing/segment-templates", headers=auth_headers)

    assert response.status_code == 200
    templates = response.json()["templates"]
    fyp1 = next((t for t in templates if t["template_id"] == "felc-unimas-fyp1"), None)
    assert fyp1 is not None
    assert fyp1["name"] == "FELC UNIMAS - FYP1 Writing Guide"
    assert fyp1["segment_count"] == 18


def test_list_segment_templates_without_authentication_returns_401(client):
    response = client.get("/writing/segment-templates")
    assert response.status_code == 401


def test_apply_segment_template_creates_all_segments(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post("/writing/segment-templates/felc-unimas-fyp1/apply", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["created"]) == 18
    assert body["skipped_existing"] == []
    assert body["limit_reached"] is False
    names = {s["name"] for s in body["created"]}
    assert "Ch1: Background of the Study" in names
    assert "Ch3: Ethical Considerations" in names

    listed = client.get("/writing/segments", headers=auth_headers)
    assert len(listed.json()["segments"]) == 18


def test_applying_a_template_twice_skips_everything_the_second_time(client, auth_headers):
    _create_workspace(client, auth_headers)
    client.post("/writing/segment-templates/felc-unimas-fyp1/apply", headers=auth_headers)

    second = client.post("/writing/segment-templates/felc-unimas-fyp1/apply", headers=auth_headers)

    assert second.status_code == 200
    body = second.json()
    assert body["created"] == []
    assert len(body["skipped_existing"]) == 18

    listed = client.get("/writing/segments", headers=auth_headers)
    assert len(listed.json()["segments"]) == 18


def test_apply_an_unknown_template_returns_404(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post("/writing/segment-templates/not-a-real-template/apply", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error_type"] == "SegmentTemplateNotFoundError"


def test_apply_for_user_with_no_agent_returns_404(client, auth_headers):
    response = client.post("/writing/segment-templates/felc-unimas-fyp1/apply", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error_type"] == "AgentNotFoundForUserError"


def test_apply_template_without_authentication_returns_401(client):
    response = client.post("/writing/segment-templates/felc-unimas-fyp1/apply")
    assert response.status_code == 401
