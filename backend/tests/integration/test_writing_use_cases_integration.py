import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.infrastructure.models import Agent
from app.modules.writing.application.use_cases import CreateDraftUseCase, CreateDraftVersionUseCase
from app.modules.writing.infrastructure.repositories import SqlAlchemyDraftRepository, SqlAlchemyDraftVersionRepository


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "writing_use_case_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()


def _make_agent(session):
    user = User(username="researcher")
    session.add(user)
    session.flush()
    agent = Agent(user_id=user.user_id)
    session.add(agent)
    session.flush()
    return agent


def test_create_draft_use_case_persists_against_real_sqlite(session):
    agent = _make_agent(session)
    use_case = CreateDraftUseCase(SqlAlchemyDraftRepository(session), SqlAlchemyUnitOfWork(session))

    draft = use_case.execute(agent_id=agent.agent_id, title="Chapter 1 Draft", target="Chapter 1")

    session.expire_all()
    fetched = SqlAlchemyDraftRepository(session).get_by_id(draft.draft_id)
    assert fetched is not None
    assert fetched.title == "Chapter 1 Draft"
    assert fetched.target == "Chapter 1"


def test_create_draft_version_use_case_persists_sequential_versions_against_real_sqlite(session):
    agent = _make_agent(session)
    draft = CreateDraftUseCase(SqlAlchemyDraftRepository(session), SqlAlchemyUnitOfWork(session)).execute(
        agent_id=agent.agent_id, title="Chapter 1 Draft"
    )

    version_use_case = CreateDraftVersionUseCase(SqlAlchemyDraftVersionRepository(session), SqlAlchemyUnitOfWork(session))
    first = version_use_case.execute(draft_id=draft.draft_id, content="Introduction paragraph.")
    second = version_use_case.execute(draft_id=draft.draft_id, content="Revised introduction paragraph.")

    session.expire_all()
    versions = SqlAlchemyDraftVersionRepository(session).list_by_draft_id(draft.draft_id)
    assert [v.version_number for v in versions] == [1, 2]
    assert first.version_id != second.version_id
