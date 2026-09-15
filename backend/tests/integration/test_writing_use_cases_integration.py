import pytest

from app.ai.exceptions import ProviderRequestError
from app.modules.knowledge.domain.enums import CreatedBy as KnowledgeCreatedBy
from app.modules.knowledge.domain.enums import KnowledgeElementType
from app.modules.knowledge.infrastructure.models import KnowledgeChunk, KnowledgeElement
from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.infrastructure.models import Agent
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.writing.application.use_cases import (
    CreateDraftUseCase,
    CreateDraftVersionUseCase,
    GenerateDraftVersionUseCase,
)
from app.modules.writing.domain.context_assembly import ContextAssemblyInput, ContextEvidence
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyDraftEvidenceLinkRepository,
    SqlAlchemyDraftRepository,
    SqlAlchemyDraftVersionRepository,
)


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


def _create_draft(session, agent, *, title="Chapter 1 Draft", target=None):
    use_case = CreateDraftUseCase(
        SqlAlchemyDraftRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    )
    return use_case.execute(user_id=agent.user_id, title=title, target=target)


class FakeTextProvider:
    def __init__(self, response: str = "Generated draft.", exception: Exception | None = None) -> None:
        self.response = response
        self.exception = exception

    def generate(self, prompt: str) -> str:
        if self.exception is not None:
            raise self.exception
        return self.response


def _make_knowledge_chunk(session, agent):
    element = KnowledgeElement(
        agent_id=agent.agent_id,
        element_type=KnowledgeElementType.CONCEPT,
        label="Evidence",
        created_by=KnowledgeCreatedBy.SYSTEM,
    )
    session.add(element)
    session.flush()
    chunk = KnowledgeChunk(agent_id=agent.agent_id,
                           element_id=element.element_id, content="Evidence content.")
    session.add(chunk)
    session.flush()
    return chunk


def _generation_context(chunk_id: int) -> ContextAssemblyInput:
    return ContextAssemblyInput(
        topic="Research topic",
        instructions="Write a grounded paragraph.",
        evidence=(ContextEvidence(chunk_id=chunk_id,
                  content="Evidence content.", summary=None, score=1.0),),
    )


def test_create_draft_use_case_persists_against_real_sqlite(session):
    agent = _make_agent(session)

    draft = _create_draft(session, agent, title="Chapter 1 Draft", target="Chapter 1")

    session.expire_all()
    fetched = SqlAlchemyDraftRepository(session).get_by_id(draft.draft_id)
    assert fetched is not None
    assert fetched.title == "Chapter 1 Draft"
    assert fetched.target == "Chapter 1"


def test_create_draft_version_use_case_persists_sequential_versions_against_real_sqlite(session):
    agent = _make_agent(session)
    draft = _create_draft(session, agent)

    version_use_case = CreateDraftVersionUseCase(
        SqlAlchemyDraftVersionRepository(session), SqlAlchemyUnitOfWork(session))
    first = version_use_case.execute(
        draft_id=draft.draft_id, content="Introduction paragraph.")
    second = version_use_case.execute(
        draft_id=draft.draft_id, content="Revised introduction paragraph.")

    session.expire_all()
    versions = SqlAlchemyDraftVersionRepository(
        session).list_by_draft_id(draft.draft_id)
    assert [v.version_number for v in versions] == [1, 2]
    assert first.version_id != second.version_id


def test_generate_draft_version_persists_content_and_evidence_links(session):
    agent = _make_agent(session)
    chunk = _make_knowledge_chunk(session, agent)
    chunk_id = chunk.chunk_id
    draft = _create_draft(session, agent)
    use_case = GenerateDraftVersionUseCase(
        SqlAlchemyDraftRepository(session),
        SqlAlchemyDraftVersionRepository(session),
        SqlAlchemyDraftEvidenceLinkRepository(session),
        FakeTextProvider(),
        SqlAlchemyUnitOfWork(session),
    )

    version = use_case.execute(
        draft_id=draft.draft_id, context=_generation_context(chunk_id))
    session.close()

    verification_session = build_sessionmaker(session.bind)()
    try:
        fetched_version = SqlAlchemyDraftVersionRepository(
            verification_session).get_by_id(version.version_id)
        links = SqlAlchemyDraftEvidenceLinkRepository(
            verification_session).list_by_draft_version_id(version.version_id)
        assert fetched_version is not None
        assert fetched_version.content == "Generated draft."
        assert fetched_version.version_number == 1
        assert len(links) == 1
        assert links[0].chunk_id == chunk_id
    finally:
        verification_session.close()


def test_provider_failure_leaves_no_generated_rows(session):
    agent = _make_agent(session)
    chunk = _make_knowledge_chunk(session, agent)
    draft = _create_draft(session, agent)
    use_case = GenerateDraftVersionUseCase(
        SqlAlchemyDraftRepository(session),
        SqlAlchemyDraftVersionRepository(session),
        SqlAlchemyDraftEvidenceLinkRepository(session),
        FakeTextProvider(exception=ProviderRequestError(
            "provider unavailable")),
        SqlAlchemyUnitOfWork(session),
    )

    with pytest.raises(ProviderRequestError):
        use_case.execute(draft_id=draft.draft_id,
                         context=_generation_context(chunk.chunk_id))

    session.expire_all()
    assert SqlAlchemyDraftVersionRepository(
        session).list_by_draft_id(draft.draft_id) == []
