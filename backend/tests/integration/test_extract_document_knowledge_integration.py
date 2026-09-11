import json

import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.application.use_cases import ExtractDocumentKnowledgeUseCase, ProcessDocumentUseCase
from app.modules.knowledge.domain.exceptions import SemanticExtractionError
from app.modules.knowledge.domain.text_extraction import PlainTextExtractor
from app.modules.knowledge.infrastructure.models import ChunkEvidenceLink, KnowledgeChunk, KnowledgeElement
from app.modules.knowledge.infrastructure.repositories import (
    SqlAlchemyChunkEvidenceLinkRepository,
    SqlAlchemyKnowledgeChunkEmbeddingRepository,
    SqlAlchemyKnowledgeChunkRepository,
    SqlAlchemyKnowledgeElementRepository,
)
from app.modules.knowledge.infrastructure.vector_models import KnowledgeChunkEmbedding
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.storage.filesystem import FilesystemStorage
from app.workers.repository import WorkItemRepository


class FakeTextGenerationProvider:
    def __init__(self, responses=None):
        self._responses = list(responses) if responses else []
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        if self._responses:
            return self._responses.pop(0)
        return '{"element_type": "concept", "label": "Default", "description": "d"}'


class FakeEmbeddingProvider:
    def __init__(self):
        self.call_count = 0

    def embed(self, text: str) -> list[float]:
        self.call_count += 1
        return [0.1, 0.2, 0.3]


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "extract_knowledge_test.db"
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


def _upload_document(session, storage, content: bytes) -> tuple[int, int]:
    """Returns (document_id, agent_id)."""
    user = User(username="researcher")
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
    return document.document_id, workspace.agent.agent_id


def _build_use_case(session, storage, provider, embedding_provider=None):
    documents = SqlAlchemyDocumentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    agents = SqlAlchemyAgentRepository(session)
    process_document = ProcessDocumentUseCase(documents, storage, PlainTextExtractor())
    elements = SqlAlchemyKnowledgeElementRepository(session)
    chunks = SqlAlchemyKnowledgeChunkRepository(session)
    links = SqlAlchemyChunkEvidenceLinkRepository(session)
    embeddings = SqlAlchemyKnowledgeChunkEmbeddingRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    return ExtractDocumentKnowledgeUseCase(
        documents,
        projects,
        agents,
        process_document,
        provider,
        embedding_provider or FakeEmbeddingProvider(),
        "test-embedding-model",
        elements,
        chunks,
        links,
        embeddings,
        uow,
    )


def test_a_real_document_is_persisted_as_genuine_evidence_linked_knowledge(session, storage):
    document_id, agent_id = _upload_document(session, storage, b"Introduction to the study.")
    provider = FakeTextGenerationProvider(
        responses=['{"element_type": "theme", "label": "Study introduction", "description": "Opens the study."}']
    )
    use_case = _build_use_case(session, storage, provider)

    result = use_case.execute(document_id=document_id)

    assert len(result) == 1
    stored_element = session.query(KnowledgeElement).filter_by(element_id=result[0].element_id).one()
    assert stored_element.element_type.value == "theme"
    assert stored_element.label == "Study introduction"
    assert stored_element.agent_id == agent_id

    stored_chunk = session.query(KnowledgeChunk).filter_by(chunk_id=result[0].chunk_id).one()
    assert stored_chunk.content == "Introduction to the study."
    assert stored_chunk.element_id == stored_element.element_id

    stored_link = session.query(ChunkEvidenceLink).filter_by(chunk_id=stored_chunk.chunk_id).one()
    assert stored_link.document_id == document_id

    stored_embedding = session.query(KnowledgeChunkEmbedding).filter_by(chunk_id=stored_chunk.chunk_id).one()
    assert json.loads(stored_embedding.embedding_vector) == [0.1, 0.2, 0.3]
    assert stored_embedding.embedding_model_version == "test-embedding-model"


def test_reprocessing_against_real_persistence_does_not_duplicate_rows(session, storage):
    document_id, _ = _upload_document(session, storage, b"Content for idempotency check.")
    provider = FakeTextGenerationProvider(
        responses=['{"element_type": "concept", "label": "X", "description": "d"}']
    )
    use_case = _build_use_case(session, storage, provider)

    use_case.execute(document_id=document_id)
    use_case.execute(document_id=document_id)

    assert session.query(KnowledgeElement).count() == 1
    assert session.query(KnowledgeChunk).count() == 1
    assert session.query(ChunkEvidenceLink).count() == 1
    assert session.query(KnowledgeChunkEmbedding).count() == 1
    assert provider.call_count == 1  # second execute did not call the provider again


def test_a_semantic_extraction_failure_leaves_no_rows_persisted(session, storage):
    document_id, _ = _upload_document(session, storage, b"Content that fails classification.")
    provider = FakeTextGenerationProvider(responses=["not valid json at all"])
    use_case = _build_use_case(session, storage, provider)

    with pytest.raises(SemanticExtractionError):
        use_case.execute(document_id=document_id)

    assert session.query(KnowledgeElement).count() == 0
    assert session.query(KnowledgeChunk).count() == 0
    assert session.query(KnowledgeChunkEmbedding).count() == 0
    assert session.query(ChunkEvidenceLink).count() == 0


def test_multiple_documents_produce_independently_evidence_linked_knowledge(session, storage):
    doc_a_id, agent_id = _upload_document(session, storage, b"Document A content.")

    # A second document under the SAME agent (same project, since one Agent owns one Project
    # permanently - ADR-009) - upload a second document into the same project instead.
    from app.modules.document.application.use_cases import UploadResearchDocumentUseCase as UploadUseCase
    from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository as ProjectsRepo

    projects = ProjectsRepo(session)
    documents = SqlAlchemyDocumentRepository(session)
    agents = SqlAlchemyAgentRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    existing_doc = documents.get_by_id(doc_a_id)
    doc_b = UploadUseCase(documents, projects, agents, storage, uow, WorkItemRepository(session)).execute(
        project_id=existing_doc.project_id,
        user_id=agents.get_by_id(agent_id).user_id,
        title="Doc B",
        format="txt",
        content=b"Document B content.",
    )

    provider = FakeTextGenerationProvider(
        responses=[
            '{"element_type": "concept", "label": "A", "description": "da"}',
            '{"element_type": "concept", "label": "B", "description": "db"}',
        ]
    )
    use_case = _build_use_case(session, storage, provider)

    result_a = use_case.execute(document_id=doc_a_id)
    result_b = use_case.execute(document_id=doc_b.document_id)

    links_a = session.query(ChunkEvidenceLink).filter_by(chunk_id=result_a[0].chunk_id).one()
    links_b = session.query(ChunkEvidenceLink).filter_by(chunk_id=result_b[0].chunk_id).one()
    assert links_a.document_id == doc_a_id
    assert links_b.document_id == doc_b.document_id
    assert result_a[0].chunk_id != result_b[0].chunk_id
