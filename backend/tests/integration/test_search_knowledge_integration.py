import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.application.retrieval import SearchKnowledgeUseCase
from app.modules.knowledge.application.use_cases import ExtractDocumentKnowledgeUseCase, ProcessDocumentUseCase
from app.modules.knowledge.domain.text_extraction import PlainTextExtractor
from app.modules.knowledge.infrastructure.repositories import (
    SqlAlchemyChunkEvidenceLinkRepository,
    SqlAlchemyKnowledgeChunkEmbeddingRepository,
    SqlAlchemyKnowledgeChunkRepository,
    SqlAlchemyKnowledgeElementRepository,
)
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.storage.filesystem import FilesystemStorage
from app.workers.repository import WorkItemRepository


class FakeTextGenerationProvider:
    def generate(self, prompt: str) -> str:
        return '{"element_type": "concept", "label": "L", "description": "d"}'


class FakeEmbeddingProvider:
    def __init__(self, vectors_by_text: dict[str, list[float]]):
        self._vectors_by_text = vectors_by_text

    def embed(self, text: str) -> list[float]:
        return self._vectors_by_text.get(text, [0.0, 0.0])


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "search_knowledge_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()


@pytest.fixture()
def storage(tmp_path):
    return FilesystemStorage(tmp_path / "object-store")


def _provision_agent_with_knowledge(session, storage, *, username: str, content: bytes, embedding_provider) -> int:
    """Uploads, processes, and semantically extracts a document for a brand-new user/agent.
    Returns the agent_id.
    """
    user = User(username=username)
    session.add(user)
    session.flush()

    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    workspace = CreateAgentWorkspaceUseCase(agents, CreateProjectUseCase(projects), uow).execute(
        user_id=user.user_id, project_title="Thesis", project_topic="Topic"
    )

    documents = SqlAlchemyDocumentRepository(session)
    document = UploadResearchDocumentUseCase(
        documents, projects, agents, storage, uow, WorkItemRepository(session)
    ).execute(project_id=workspace.project.project_id, user_id=user.user_id, title="Doc", format="txt", content=content)

    process_document = ProcessDocumentUseCase(documents, storage, PlainTextExtractor())
    ExtractDocumentKnowledgeUseCase(
        documents,
        projects,
        agents,
        process_document,
        FakeTextGenerationProvider(),
        embedding_provider,
        "test-embedding-model",
        SqlAlchemyKnowledgeElementRepository(session),
        SqlAlchemyKnowledgeChunkRepository(session),
        SqlAlchemyChunkEvidenceLinkRepository(session),
        SqlAlchemyKnowledgeChunkEmbeddingRepository(session),
        uow,
    ).execute(document_id=document.document_id)

    return workspace.agent.agent_id, user.user_id, document.document_id


def _build_search_use_case(session, embedding_provider):
    return SearchKnowledgeUseCase(
        SqlAlchemyAgentRepository(session),
        embedding_provider,
        SqlAlchemyKnowledgeChunkEmbeddingRepository(session),
        SqlAlchemyKnowledgeChunkRepository(session),
        SqlAlchemyChunkEvidenceLinkRepository(session),
        SqlAlchemyDocumentRepository(session),
    )


def test_full_pipeline_to_search_with_real_persistence(session, storage):
    embedding_provider = FakeEmbeddingProvider(
        {"About coastal erosion research.": [1.0, 0.0], "search query about coastal erosion": [1.0, 0.0]}
    )
    agent_id, user_id, document_id = _provision_agent_with_knowledge(
        session, storage, username="researcher", content=b"About coastal erosion research.", embedding_provider=embedding_provider
    )

    search_use_case = _build_search_use_case(session, embedding_provider)
    results = search_use_case.execute(user_id=user_id, query="search query about coastal erosion")

    assert len(results) == 1
    assert results[0].content == "About coastal erosion research."
    assert results[0].evidence[0].document_id == document_id
    assert results[0].score == pytest.approx(1.0)


def test_search_against_an_empty_knowledge_base_returns_no_results(session, storage):
    user = User(username="empty-researcher")
    session.add(user)
    session.flush()
    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    CreateAgentWorkspaceUseCase(agents, CreateProjectUseCase(projects), uow).execute(
        user_id=user.user_id, project_title="Thesis", project_topic="Topic"
    )

    search_use_case = _build_search_use_case(session, FakeEmbeddingProvider({}))
    results = search_use_case.execute(user_id=user.user_id, query="anything")

    assert results == []


def test_agent_a_cannot_retrieve_agent_bs_knowledge_against_real_persistence(session, storage):
    """The explicit authorization requirement: real persisted knowledge for two distinct
    agents, proven never to cross agent boundaries via real SQLAlchemy queries.
    """
    embedding_provider = FakeEmbeddingProvider(
        {
            "Agent A's confidential research.": [1.0, 0.0],
            "Agent B's confidential research.": [1.0, 0.0],  # deliberately identical vector
            "confidential research query": [1.0, 0.0],
        }
    )
    agent_a_id, user_a_id, _ = _provision_agent_with_knowledge(
        session, storage, username="researcher-a", content=b"Agent A's confidential research.", embedding_provider=embedding_provider
    )
    agent_b_id, user_b_id, _ = _provision_agent_with_knowledge(
        session, storage, username="researcher-b", content=b"Agent B's confidential research.", embedding_provider=embedding_provider
    )

    assert agent_a_id != agent_b_id

    search_use_case = _build_search_use_case(session, embedding_provider)
    results_for_a = search_use_case.execute(user_id=user_a_id, query="confidential research query")

    assert len(results_for_a) == 1
    assert results_for_a[0].content == "Agent A's confidential research."
    assert "Agent B" not in results_for_a[0].content
