import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.application.use_cases import ProcessDocumentUseCase
from app.modules.knowledge.domain.exceptions import EmptyExtractedTextError, UnsupportedDocumentFormatError
from app.modules.knowledge.domain.text_extraction import PlainTextExtractor
from app.modules.knowledge.infrastructure.models import ChunkEvidenceLink, KnowledgeChunk, KnowledgeElement
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.storage.filesystem import FilesystemStorage
from app.workers.repository import WorkItemRepository


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "process_document_test.db"
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


def _upload_document(session, storage, content: bytes, *, format: str = "txt") -> int:
    user = User(username="researcher")
    session.add(user)
    session.flush()

    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    create_project = CreateProjectUseCase(projects)
    workspace = CreateAgentWorkspaceUseCase(agents, create_project, uow).execute(
        user_id=user.user_id, project_title="Thesis", project_topic="Topic"
    )

    documents = SqlAlchemyDocumentRepository(session)
    upload_use_case = UploadResearchDocumentUseCase(documents, projects, agents, storage, uow, WorkItemRepository(session))
    document = upload_use_case.execute(
        project_id=workspace.project.project_id,
        user_id=user.user_id,
        title="Baseline survey",
        format=format,
        content=content,
    )
    return document.document_id


def test_a_real_uploaded_document_is_processed_into_traceable_chunks(session, storage):
    document_id = _upload_document(session, storage, b"Introduction.\n\nMethodology follows.")

    documents = SqlAlchemyDocumentRepository(session)
    use_case = ProcessDocumentUseCase(documents, storage, PlainTextExtractor())
    chunks = use_case.execute(document_id=document_id)

    assert len(chunks) == 1
    assert chunks[0].text == "Introduction.\n\nMethodology follows."
    assert chunks[0].document_id == document_id


def test_every_chunk_can_be_traced_back_to_its_research_document(session, storage):
    """The central Stage 4 question: 'Which Research Document produced this chunk?' -
    trivially answerable here since TextChunkCandidate.document_id is always the input
    document_id, verified against the real persisted document row.
    """
    document_id = _upload_document(session, storage, b"Some source content for evidence tracing.")

    documents = SqlAlchemyDocumentRepository(session)
    use_case = ProcessDocumentUseCase(documents, storage, PlainTextExtractor())
    chunks = use_case.execute(document_id=document_id)

    stored_document = documents.get_by_id(document_id)
    assert stored_document is not None
    assert all(chunk.document_id == stored_document.document_id for chunk in chunks)


def test_processing_creates_no_knowledge_element_chunk_or_evidence_link_rows(session, storage):
    """Explicit negative assertion: Stage 4 performs no semantic interpretation and must not
    create any of the three persisted knowledge entities.
    """
    document_id = _upload_document(session, storage, b"Content that must not become a fake concept.")

    documents = SqlAlchemyDocumentRepository(session)
    use_case = ProcessDocumentUseCase(documents, storage, PlainTextExtractor())
    use_case.execute(document_id=document_id)

    assert session.query(KnowledgeElement).count() == 0
    assert session.query(KnowledgeChunk).count() == 0
    assert session.query(ChunkEvidenceLink).count() == 0


def test_processing_does_not_change_the_documents_processing_status(session, storage):
    document_id = _upload_document(session, storage, b"Content for status-stability check.")

    documents = SqlAlchemyDocumentRepository(session)
    before = documents.get_by_id(document_id).processing_status
    use_case = ProcessDocumentUseCase(documents, storage, PlainTextExtractor())
    use_case.execute(document_id=document_id)

    session.expire_all()
    after = documents.get_by_id(document_id).processing_status
    assert before == after


def test_processing_a_binary_format_document_fails_extraction(session, storage):
    document_id = _upload_document(session, storage, b"%PDF-1.4\n\xe2\xe3\xcf\xd3\x00\x01\x02", format="pdf")

    documents = SqlAlchemyDocumentRepository(session)
    use_case = ProcessDocumentUseCase(documents, storage, PlainTextExtractor())

    with pytest.raises(UnsupportedDocumentFormatError):
        use_case.execute(document_id=document_id)

    assert session.query(KnowledgeChunk).count() == 0


def test_reprocessing_against_real_persistence_produces_identical_chunks_each_time(session, storage):
    document_id = _upload_document(session, storage, b"Repeatable content.\n\nSecond paragraph.")

    documents = SqlAlchemyDocumentRepository(session)
    use_case = ProcessDocumentUseCase(documents, storage, PlainTextExtractor())

    first = use_case.execute(document_id=document_id)
    second = use_case.execute(document_id=document_id)

    assert [c.text for c in first] == [c.text for c in second]
    assert session.query(KnowledgeChunk).count() == 0  # still nothing persisted, either time


def test_empty_uploaded_document_content_is_rejected_before_persistence_would_be_needed(session, storage, tmp_path):
    """Upload itself already rejects empty content (EmptyDocumentContentError, Stage 1) - this
    test instead exercises the case where stored bytes decode to only whitespace, which
    upload's own validation cannot catch (it validates non-empty bytes, not their meaning).
    """
    document_id = _upload_document(session, storage, b"   \n\n\t  ")

    documents = SqlAlchemyDocumentRepository(session)
    use_case = ProcessDocumentUseCase(documents, storage, PlainTextExtractor())

    with pytest.raises(EmptyExtractedTextError):
        use_case.execute(document_id=document_id)
