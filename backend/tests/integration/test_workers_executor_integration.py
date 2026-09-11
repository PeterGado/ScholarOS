import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.domain.enums import DocumentProcessingStatus
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.infrastructure.models import ChunkEvidenceLink, KnowledgeChunk, KnowledgeElement
from app.modules.knowledge.infrastructure.vector_models import KnowledgeChunkEmbedding
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.storage.filesystem import FilesystemStorage
from app.workers.enums import WorkItemKind, WorkItemState
from app.workers.executor import process_one_work_item
from app.workers.payloads import build_process_document_payload_reference
from app.workers.repository import WorkItemRepository


class FakeTextGenerationProvider:
    def __init__(self, responses=None, always_fail=False):
        self._responses = list(responses) if responses else []
        self._always_fail = always_fail
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        if self._always_fail:
            raise RuntimeError("simulated provider outage")
        if self._responses:
            return self._responses.pop(0)
        return '{"element_type": "concept", "label": "Default", "description": "d"}'


class FakeEmbeddingProvider:
    def __init__(self, always_fail=False):
        self._always_fail = always_fail
        self.call_count = 0

    def embed(self, text: str) -> list[float]:
        self.call_count += 1
        if self._always_fail:
            raise RuntimeError("simulated embedding outage")
        return [0.1, 0.2, 0.3]


def _process_one(session, storage, *, text_provider, embedding_provider=None) -> bool:
    return process_one_work_item(
        session,
        text_provider=text_provider,
        embedding_provider=embedding_provider or FakeEmbeddingProvider(),
        embedding_model_version="test-embedding-model",
        storage=storage,
    )


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "workers_executor_test.db"
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


def _upload_document(session, storage, content: bytes = b"Some real document content.") -> int:
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
    return document.document_id


# --- WorkItemRepository, directly ------------------------------------------------------


def test_upload_enqueues_exactly_one_queued_work_item(session, storage):
    document_id = _upload_document(session, storage)

    work_items = WorkItemRepository(session)
    item = work_items.claim_next_queued()

    assert item is not None
    assert item.kind == WorkItemKind.PIPELINE_STAGE
    assert item.payload_reference == build_process_document_payload_reference(document_id)
    assert item.state == WorkItemState.RUNNING  # claim_next_queued transitions it
    assert work_items.claim_next_queued() is None  # nothing else queued


def test_claiming_an_empty_queue_returns_none(session, storage):
    assert WorkItemRepository(session).claim_next_queued() is None


def test_mark_failed_requeues_until_max_attempts_then_terminates(session, storage):
    _upload_document(session, storage)
    work_items = WorkItemRepository(session)
    item = work_items.claim_next_queued()

    updated = work_items.mark_failed(item.work_item_id, error="boom")
    assert updated.state == WorkItemState.QUEUED
    assert updated.attempts == 1

    reclaimed = work_items.claim_next_queued()
    updated = work_items.mark_failed(reclaimed.work_item_id, error="boom again")
    assert updated.state == WorkItemState.QUEUED
    assert updated.attempts == 2

    reclaimed = work_items.claim_next_queued()
    updated = work_items.mark_failed(reclaimed.work_item_id, error="final failure")
    assert updated.state == WorkItemState.FAILED
    assert updated.attempts == 3
    assert updated.completed_at is not None


# --- process_one_work_item, end to end ----------------------------------------------------


def test_process_one_work_item_returns_false_on_an_empty_queue(session, storage):
    provider = FakeTextGenerationProvider()
    assert _process_one(session, storage, text_provider=provider) is False


def test_process_one_work_item_succeeds_and_transitions_document_to_processed(session, storage):
    document_id = _upload_document(session, storage, content=b"Paragraph one.\n\nParagraph two.")
    provider = FakeTextGenerationProvider(
        responses=['{"element_type": "theme", "label": "Overview", "description": "d"}']
    )

    claimed = _process_one(session, storage, text_provider=provider)

    assert claimed is True
    session.expire_all()
    documents = SqlAlchemyDocumentRepository(session)
    document = documents.get_by_id(document_id)
    assert document.processing_status == DocumentProcessingStatus.PROCESSED
    assert document.processed_at is not None

    assert session.query(KnowledgeElement).count() == 1
    assert session.query(KnowledgeChunk).count() == 1
    assert session.query(ChunkEvidenceLink).count() == 1
    assert session.query(KnowledgeChunkEmbedding).count() == 1

    work_items = WorkItemRepository(session)
    assert work_items.claim_next_queued() is None  # the item is now succeeded, not queued


def test_process_one_work_item_embedding_failure_requeues_like_any_other_pipeline_failure(session, storage):
    document_id = _upload_document(session, storage)
    provider = FakeTextGenerationProvider()
    embedding_provider = FakeEmbeddingProvider(always_fail=True)

    _process_one(session, storage, text_provider=provider, embedding_provider=embedding_provider)

    session.expire_all()
    documents = SqlAlchemyDocumentRepository(session)
    document = documents.get_by_id(document_id)
    assert document.processing_status == DocumentProcessingStatus.PENDING

    assert session.query(KnowledgeElement).count() == 0
    assert session.query(KnowledgeChunk).count() == 0
    assert session.query(KnowledgeChunkEmbedding).count() == 0


def test_process_one_work_item_failure_sets_document_pending_while_retry_is_possible(session, storage):
    document_id = _upload_document(session, storage)
    provider = FakeTextGenerationProvider(always_fail=True)

    _process_one(session, storage, text_provider=provider)

    session.expire_all()
    documents = SqlAlchemyDocumentRepository(session)
    document = documents.get_by_id(document_id)
    assert document.processing_status == DocumentProcessingStatus.PENDING  # requeued, not yet exhausted

    assert session.query(KnowledgeElement).count() == 0
    assert session.query(KnowledgeChunk).count() == 0


def test_process_one_work_item_sets_document_failed_after_exhausting_retries(session, storage):
    document_id = _upload_document(session, storage)
    provider = FakeTextGenerationProvider(always_fail=True)

    for _ in range(3):  # DEFAULT_MAX_ATTEMPTS
        _process_one(session, storage, text_provider=provider)

    session.expire_all()
    documents = SqlAlchemyDocumentRepository(session)
    document = documents.get_by_id(document_id)
    assert document.processing_status == DocumentProcessingStatus.FAILED

    work_items = WorkItemRepository(session)
    assert work_items.claim_next_queued() is None  # terminal, never queued again
    assert session.query(KnowledgeElement).count() == 0


def test_a_second_process_one_work_item_call_after_success_finds_nothing_to_claim(session, storage):
    _upload_document(session, storage)
    provider = FakeTextGenerationProvider()

    assert _process_one(session, storage, text_provider=provider) is True
    assert _process_one(session, storage, text_provider=provider) is False
