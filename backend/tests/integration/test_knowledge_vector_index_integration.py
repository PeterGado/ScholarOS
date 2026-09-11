import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.application.use_cases import ExtractDocumentKnowledgeUseCase, ProcessDocumentUseCase
from app.modules.knowledge.domain.text_extraction import PlainTextExtractor
from app.modules.knowledge.domain.vector_similarity import rank_by_similarity
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
    """Returns a distinct, hand-chosen vector per known input, so the test can assert a
    specific, predictable similarity ranking - not just "a ranking exists".
    """

    def __init__(self, vectors_by_text: dict[str, list[float]]):
        self._vectors_by_text = vectors_by_text

    def embed(self, text: str) -> list[float]:
        return self._vectors_by_text[text]


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "vector_index_test.db"
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


def _upload_and_process(session, storage, content: bytes, embedding_provider) -> tuple[int, int]:
    """Returns (document_id, agent_id)."""
    user = User(username=f"researcher-{content!r}")
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
    extract_use_case = ExtractDocumentKnowledgeUseCase(
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
    )
    extract_use_case.execute(document_id=document.document_id)
    return document.document_id, workspace.agent.agent_id


def test_a_persisted_chunk_is_retrievable_by_similarity_against_a_real_query_vector(session, storage):
    embedding_provider = FakeEmbeddingProvider(
        {
            "About coastal erosion.": [1.0, 0.0, 0.0],
            "About unrelated topic entirely.": [0.0, 1.0, 0.0],
        }
    )
    _, agent_id = _upload_and_process(session, storage, b"About coastal erosion.", embedding_provider)
    _upload_and_process(session, storage, b"About unrelated topic entirely.", embedding_provider)

    # This is the OTHER agent's data too - list_by_agent_id must not scope to it.
    embeddings_repo = SqlAlchemyKnowledgeChunkEmbeddingRepository(session)
    candidates = embeddings_repo.list_by_agent_id(agent_id)

    assert len(candidates) == 1  # only the first agent's own chunk

    query_vector = [1.0, 0.0, 0.0]  # matches "coastal erosion" exactly
    ranked = rank_by_similarity(query_vector, candidates)

    assert len(ranked) == 1
    assert ranked[0][1] == pytest.approx(1.0)


def test_similarity_ranking_across_an_agents_own_multiple_chunks(session, storage):
    embedding_provider = FakeEmbeddingProvider(
        {
            "Closely related content.": [0.9, 0.1],
            "Distantly related content.": [0.1, 0.9],
        }
    )
    doc_a_id, agent_id = _upload_and_process(session, storage, b"Closely related content.", embedding_provider)

    # A second document for the SAME agent's project (one Agent = one Project, ADR-009) -
    # upload directly into the same project as doc_a.
    documents = SqlAlchemyDocumentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    agents = SqlAlchemyAgentRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    existing_doc = documents.get_by_id(doc_a_id)
    doc_b = UploadResearchDocumentUseCase(
        documents, projects, agents, storage, uow, WorkItemRepository(session)
    ).execute(
        project_id=existing_doc.project_id,
        user_id=agents.get_by_id(agent_id).user_id,
        title="Doc B",
        format="txt",
        content=b"Distantly related content.",
    )
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
    ).execute(document_id=doc_b.document_id)

    candidates = SqlAlchemyKnowledgeChunkEmbeddingRepository(session).list_by_agent_id(agent_id)
    assert len(candidates) == 2

    query_vector = [1.0, 0.0]  # closer to the "closely related" chunk
    ranked = rank_by_similarity(query_vector, candidates)

    assert ranked[0][1] > ranked[1][1]  # the closely-related chunk ranks first
