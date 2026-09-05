import pytest
from sqlalchemy.exc import IntegrityError

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.domain.exceptions import AgentAlreadyExistsForUserError
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.domain.exceptions import InvalidProjectTopicError
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "workspace_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()


def _make_user(session, username="researcher"):
    user = User(username=username)
    session.add(user)
    session.flush()
    return user


def _build_use_case(session):
    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    create_project = CreateProjectUseCase(projects)
    return CreateAgentWorkspaceUseCase(agents, create_project, uow), agents, projects


def test_workspace_creation_persists_agent_and_project_atomically(session):
    user = _make_user(session)
    use_case, agents, projects = _build_use_case(session)

    workspace = use_case.execute(user_id=user.user_id, project_title="Thesis", project_topic="Coastal erosion")

    session.expire_all()
    stored_agent = agents.get_by_user_id(user.user_id)
    stored_project = projects.get_by_agent_id(stored_agent.agent_id)
    assert stored_agent.agent_id == workspace.agent.agent_id
    assert stored_project.project_id == workspace.project.project_id
    assert stored_project.topic == "Coastal erosion"


def test_one_agent_per_user_is_enforced_against_real_persisted_state(session):
    user = _make_user(session)
    use_case, _, _ = _build_use_case(session)
    use_case.execute(user_id=user.user_id, project_title="Thesis", project_topic="Topic A")

    with pytest.raises(AgentAlreadyExistsForUserError):
        use_case.execute(user_id=user.user_id, project_title="Second", project_topic="Topic B")


def test_a_project_creation_failure_rolls_back_the_already_flushed_agent(session):
    """Project.create() raises InvalidProjectTopicError for a blank topic *after* the Agent
    has already been added+flushed inside the use case. The use case must roll back so no
    orphaned Agent (one without its permanent Project) is left committed - invariant 15.
    """
    user = _make_user(session)
    use_case, agents, projects = _build_use_case(session)

    with pytest.raises(InvalidProjectTopicError):
        use_case.execute(user_id=user.user_id, project_title="Thesis", project_topic="   ")

    # The use case already rolled back internally (its except-clause calls uow.rollback()
    # before re-raising) - confirm the flushed-but-never-committed Agent did not survive.
    assert agents.get_by_user_id(user.user_id) is None


def test_project_agent_id_uniqueness_is_still_enforced_at_the_database_level(session):
    """Belt-and-suspenders: even if application logic were bypassed, the DB constraint from
    Stage 3 (Project.agent_id unique) still holds.
    """
    user = _make_user(session)
    use_case, agents, projects = _build_use_case(session)
    workspace = use_case.execute(user_id=user.user_id, project_title="Thesis", project_topic="Topic A")

    from app.modules.project.infrastructure.models import Project as ProjectModel

    session.add(ProjectModel(agent_id=workspace.agent.agent_id, title="Duplicate", topic="Topic B"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
