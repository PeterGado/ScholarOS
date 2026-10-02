from app.auth.hashing import hash_password
from app.database.session import build_sessionmaker
from app.database.shared_models import User


def _create_workspace(client, headers) -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Coastal erosion"}, headers=headers)
    return response.json()


def test_create_segment_returns_201_with_expected_schema(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post(
        "/writing/segments",
        json={"name": "Background of the Study", "instructions": "Always cite at least two sources."},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Background of the Study"
    assert body["instructions"] == "Always cite at least two sources."
    assert isinstance(body["segment_id"], int)
    assert body["updated_at"] is None


def test_create_segment_without_authentication_returns_401(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post("/writing/segments", json={"name": "Background", "instructions": "x"})

    assert response.status_code == 401


def test_create_segment_for_user_with_no_agent_returns_404(client, auth_headers):
    response = client.post("/writing/segments", json={"name": "Background", "instructions": "x"}, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error_type"] == "AgentNotFoundForUserError"


def test_create_segment_with_blank_name_returns_422(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post("/writing/segments", json={"name": "   ", "instructions": "x"}, headers=auth_headers)

    assert response.status_code == 422


def test_create_segment_with_a_duplicate_name_returns_409(client, auth_headers):
    _create_workspace(client, auth_headers)
    client.post("/writing/segments", json={"name": "Background", "instructions": "x"}, headers=auth_headers)

    response = client.post("/writing/segments", json={"name": "Background", "instructions": "y"}, headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["error_type"] == "DuplicateWritingSegmentNameError"


def test_create_segment_past_the_limit_returns_409(client, auth_headers, monkeypatch):
    import app.modules.writing.application.segments as segments_module

    monkeypatch.setattr(segments_module, "MAX_WRITING_SEGMENTS_PER_AGENT", 1)
    _create_workspace(client, auth_headers)
    client.post("/writing/segments", json={"name": "First", "instructions": "x"}, headers=auth_headers)

    response = client.post("/writing/segments", json={"name": "Second", "instructions": "y"}, headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["error_type"] == "TooManyWritingSegmentsError"


def test_list_segments_returns_them_alphabetically(client, auth_headers):
    _create_workspace(client, auth_headers)
    client.post("/writing/segments", json={"name": "Zeta section", "instructions": "x"}, headers=auth_headers)
    client.post("/writing/segments", json={"name": "Alpha section", "instructions": "y"}, headers=auth_headers)

    response = client.get("/writing/segments", headers=auth_headers)

    assert response.status_code == 200
    names = [s["name"] for s in response.json()["segments"]]
    assert names == ["Alpha section", "Zeta section"]


def test_list_segments_is_empty_for_a_fresh_workspace(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.get("/writing/segments", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["segments"] == []


def test_update_segment_changes_name_and_instructions(client, auth_headers):
    _create_workspace(client, auth_headers)
    created = client.post(
        "/writing/segments", json={"name": "Background", "instructions": "Old."}, headers=auth_headers
    ).json()

    response = client.patch(
        f"/writing/segments/{created['segment_id']}",
        json={"name": "Background of the Study", "instructions": "New."},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Background of the Study"
    assert body["instructions"] == "New."
    assert body["updated_at"] is not None


def test_update_a_nonexistent_segment_returns_404(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.patch(
        "/writing/segments/999999", json={"name": "X", "instructions": "Y"}, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["error_type"] == "WritingSegmentNotFoundError"


def test_update_a_segment_belonging_to_another_user_returns_404(client, db_engine, auth_headers):
    _create_workspace(client, auth_headers)
    created = client.post(
        "/writing/segments", json={"name": "Background", "instructions": "x"}, headers=auth_headers
    ).json()

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post("/agents", json={"project_title": "Intruder Thesis", "project_topic": "Other"}, headers=intruder_headers)

    response = client.patch(
        f"/writing/segments/{created['segment_id']}",
        json={"name": "X", "instructions": "Y"},
        headers=intruder_headers,
    )

    assert response.status_code == 404
    assert response.json()["error_type"] == "WritingSegmentNotFoundError"


def test_update_rejects_renaming_to_another_segments_existing_name(client, auth_headers):
    _create_workspace(client, auth_headers)
    client.post("/writing/segments", json={"name": "Background", "instructions": "x"}, headers=auth_headers)
    second = client.post(
        "/writing/segments", json={"name": "Methodology", "instructions": "y"}, headers=auth_headers
    ).json()

    response = client.patch(
        f"/writing/segments/{second['segment_id']}",
        json={"name": "Background", "instructions": "y"},
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["error_type"] == "DuplicateWritingSegmentNameError"


def test_delete_segment_removes_it_from_the_list(client, auth_headers):
    _create_workspace(client, auth_headers)
    created = client.post(
        "/writing/segments", json={"name": "Background", "instructions": "x"}, headers=auth_headers
    ).json()

    response = client.delete(f"/writing/segments/{created['segment_id']}", headers=auth_headers)

    assert response.status_code == 204
    listed = client.get("/writing/segments", headers=auth_headers)
    assert listed.json()["segments"] == []


def test_delete_a_nonexistent_segment_returns_404(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.delete("/writing/segments/999999", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error_type"] == "WritingSegmentNotFoundError"
