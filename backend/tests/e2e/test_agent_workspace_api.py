from app.database.session import build_sessionmaker
from app.database.shared_models import User
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from tests.e2e.conftest import AUTH_USERNAME


def test_create_agent_workspace_returns_201_with_expected_schema(client, auth_headers):
    response = client.post(
        "/agents",
        json={"project_title": "Thesis", "project_topic": "Coastal erosion", "project_description": "Notes"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["agent"]["status"] == "active"
    assert isinstance(body["agent"]["agent_id"], int)
    assert body["project"]["topic"] == "Coastal erosion"
    assert body["project"]["agent_id"] == body["agent"]["agent_id"]
    assert body["project"]["description"] == "Notes"


def test_create_agent_workspace_persists_to_database(client, db_engine, auth_headers):
    response = client.post(
        "/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=auth_headers
    )
    agent_id = response.json()["agent"]["agent_id"]

    session = build_sessionmaker(db_engine)()
    try:
        agents = SqlAlchemyAgentRepository(session)
        projects = SqlAlchemyProjectRepository(session)
        stored_agent = agents.get_by_id(agent_id)
        stored_project = projects.get_by_agent_id(agent_id)
        assert stored_agent is not None
        assert stored_project is not None
        assert stored_project.topic == "Topic"
    finally:
        session.close()


def test_create_agent_workspace_without_authentication_returns_401(client):
    """Stage 6: POST /agents no longer resolves to a bootstrap identity."""
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"})
    assert response.status_code == 401
    assert response.json()["error_type"] == "InvalidSessionError"


def test_client_supplied_user_id_cannot_override_the_authenticated_identity(client, auth_headers):
    """The request body has no user_id field at all - CreateAgentWorkspaceRequest only
    accepts project_title/topic/description (Stage 6 Phase 4). Supplying one is simply
    ignored by Pydantic's schema, not honored as an identity override.
    """
    response = client.post(
        "/agents",
        json={"project_title": "Thesis", "project_topic": "Topic", "user_id": 999999},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["agent"]["agent_id"] != 999999


def test_second_call_for_the_same_authenticated_user_returns_409(client, auth_headers):
    first = client.post("/agents", json={"project_title": "First", "project_topic": "Topic A"}, headers=auth_headers)
    assert first.status_code == 201

    second = client.post(
        "/agents", json={"project_title": "Second", "project_topic": "Topic B"}, headers=auth_headers
    )
    assert second.status_code == 409
    body = second.json()
    assert body["error_type"] == "AgentAlreadyExistsForUserError"
    assert "detail" in body


def test_blank_topic_reaching_domain_validation_returns_422(client, auth_headers):
    """Whitespace-only passes Pydantic's min_length=1 but fails Project's own domain
    invariant - confirms the API doesn't duplicate that rule, just translates it.
    """
    response = client.post(
        "/agents", json={"project_title": "Thesis", "project_topic": "   "}, headers=auth_headers
    )
    assert response.status_code == 422
    assert response.json()["error_type"] == "InvalidProjectTopicError"


def test_missing_required_field_is_rejected_before_reaching_the_use_case(client, auth_headers):
    response = client.post("/agents", json={"project_title": "Thesis"}, headers=auth_headers)
    assert response.status_code == 422


def test_created_agent_belongs_to_the_authenticated_provisioned_user(client, db_engine, auth_headers):
    response = client.post(
        "/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=auth_headers
    )
    agent_id = response.json()["agent"]["agent_id"]

    session = build_sessionmaker(db_engine)()
    try:
        provisioned_user = session.query(User).filter_by(username=AUTH_USERNAME).one()
        agents = SqlAlchemyAgentRepository(session)
        stored_agent = agents.get_by_id(agent_id)
        assert stored_agent.user_id == provisioned_user.user_id
    finally:
        session.close()


def test_no_bootstrap_user_is_created_by_an_authenticated_request(client, db_engine, auth_headers):
    """Stage 6: the only User row in existence after this flow is the provisioned account -
    no second, implicitly-created 'default-user' row.
    """
    client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=auth_headers)

    session = build_sessionmaker(db_engine)()
    try:
        usernames = {u.username for u in session.query(User).all()}
        assert usernames == {AUTH_USERNAME}
        assert "default-user" not in usernames
    finally:
        session.close()
