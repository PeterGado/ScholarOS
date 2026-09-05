from app.database.session import build_sessionmaker
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository


def test_create_agent_workspace_returns_201_with_expected_schema(client):
    response = client.post(
        "/agents",
        json={"project_title": "Thesis", "project_topic": "Coastal erosion", "project_description": "Notes"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["agent"]["status"] == "active"
    assert isinstance(body["agent"]["agent_id"], int)
    assert body["project"]["topic"] == "Coastal erosion"
    assert body["project"]["agent_id"] == body["agent"]["agent_id"]
    assert body["project"]["description"] == "Notes"


def test_create_agent_workspace_persists_to_database(client, db_engine):
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"})
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


def test_second_call_for_the_single_bootstrap_user_returns_409(client):
    """The MVP is single-user (invariant 9) and this stage has no auth, so every request
    resolves to the same bootstrap user - a second call is therefore always a genuine
    duplicate-Agent-for-User case, exercised here over real HTTP.
    """
    first = client.post("/agents", json={"project_title": "First", "project_topic": "Topic A"})
    assert first.status_code == 201

    second = client.post("/agents", json={"project_title": "Second", "project_topic": "Topic B"})
    assert second.status_code == 409
    body = second.json()
    assert body["error_type"] == "AgentAlreadyExistsForUserError"
    assert "detail" in body


def test_blank_topic_reaching_domain_validation_returns_422(client):
    """Whitespace-only passes Pydantic's min_length=1 but fails Project's own domain
    invariant - confirms the API doesn't duplicate that rule, just translates it.
    """
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "   "})
    assert response.status_code == 422
    assert response.json()["error_type"] == "InvalidProjectTopicError"


def test_missing_required_field_is_rejected_before_reaching_the_use_case(client):
    response = client.post("/agents", json={"project_title": "Thesis"})
    assert response.status_code == 422
