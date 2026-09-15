import asyncio
from datetime import timedelta

import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.domain.entities import Agent
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.domain.enums import DocumentProcessingStatus
from app.modules.document.infrastructure.models import ResearchDocument
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.infrastructure.models import ChunkEvidenceLink, KnowledgeChunk, KnowledgeElement
from app.modules.knowledge.domain.enums import CreatedBy as KnowledgeCreatedBy, KnowledgeElementType
from app.modules.knowledge.infrastructure.vector_models import KnowledgeChunkEmbedding
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.application.use_cases import CreateDraftUseCase
from app.modules.writing.domain.context_assembly import ContextAssemblyInput, ContextEvidence
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyDraftRepository,
    SqlAlchemyDraftVersionRepository,
)
from app.modules.writing.infrastructure.models import DraftEvidenceLink
from app.storage.filesystem import FilesystemStorage
from app.workers.enums import WorkItemKind, WorkItemState
from app.workers.executor import WorkItemExecutorLoop, process_one_work_item
from app.workers.models import WorkItem as WorkItemModel
from app.workers.payloads import build_generate_draft_version_payload_reference, build_process_document_payload_reference
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


@pytest.fixture()
def session_factory(tmp_path):
    """A real callable factory (distinct from the single-session `session` fixture above) -
    `WorkItemExecutorLoop` needs to open a fresh session per work item/recovery pass, exactly
    as `main.py` wires it against `db_session_module.SessionLocal`.
    """
    db_path = tmp_path / "workers_executor_loop_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    factory = build_sessionmaker(engine)
    try:
        yield factory
    finally:
        engine.dispose()


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


def _enqueue_writing_generation(session, storage, *, request_id="writing-request-1", with_instructions_message=False):
    user = User(username=f"writer-{request_id}")
    session.add(user)
    session.flush()
    agent = SqlAlchemyAgentRepository(session).add(Agent(user_id=user.user_id))
    session.flush()

    message_id = None
    if with_instructions_message:
        from app.modules.writing.domain.entities import Conversation, Message
        from app.modules.writing.domain.enums import MessageDirection
        from app.modules.writing.infrastructure.repositories import (
            SqlAlchemyConversationRepository,
            SqlAlchemyMessageRepository,
        )

        conversation = SqlAlchemyConversationRepository(session).add(
            Conversation(agent_id=agent.agent_id, title=f"draft:{request_id}:instructions")
        )
        message = SqlAlchemyMessageRepository(session).add(
            Message(
                conversation_id=conversation.conversation_id,
                sequence=1,
                direction=MessageDirection.USER_REQUEST,
                content="Write a grounded paragraph.",
            )
        )
        session.flush()
        message_id = message.message_id
    element = KnowledgeElement(
        agent_id=agent.agent_id,
        element_type=KnowledgeElementType.CONCEPT,
        label="Evidence",
        created_by=KnowledgeCreatedBy.SYSTEM,
    )
    session.add(element)
    session.flush()
    # Realistic, evidence-sized content (not a one-line fixture string) - this is the exact
    # scenario the fixed defect broke: a context this size used to be inlined into
    # payload_reference and rejected once it exceeded 512 characters.
    chunk = KnowledgeChunk(
        agent_id=agent.agent_id, element_id=element.element_id, content="Evidence paragraph. " * 100
    )
    session.add(chunk)
    session.flush()
    draft = CreateDraftUseCase(
        SqlAlchemyDraftRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=user.user_id, title="Generated Draft")
    context = ContextAssemblyInput(
        topic="Research topic",
        instructions="Write a grounded paragraph.",
        evidence=(ContextEvidence(chunk_id=chunk.chunk_id,
                  content=chunk.content, summary=None, score=1.0),),
    )
    payload, idempotency_key = build_generate_draft_version_payload_reference(
        draft.draft_id, context, storage, request_id=request_id, message_id=message_id
    )
    assert len(payload) < 200  # a genuine reference, not the inlined context
    WorkItemRepository(session).enqueue(
        kind=WorkItemKind.PIPELINE_STAGE,
        payload_reference=payload,
        idempotency_key=idempotency_key,
    )
    SqlAlchemyUnitOfWork(session).commit()
    return draft.draft_id, chunk.chunk_id, request_id, message_id


# --- WorkItemRepository, directly ------------------------------------------------------


def test_upload_enqueues_exactly_one_queued_work_item(session, storage):
    document_id = _upload_document(session, storage)

    work_items = WorkItemRepository(session)
    item = work_items.claim_next_queued()

    assert item is not None
    assert item.kind == WorkItemKind.PIPELINE_STAGE
    assert item.payload_reference == build_process_document_payload_reference(
        document_id)
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
    updated = work_items.mark_failed(
        reclaimed.work_item_id, error="boom again")
    assert updated.state == WorkItemState.QUEUED
    assert updated.attempts == 2

    reclaimed = work_items.claim_next_queued()
    updated = work_items.mark_failed(
        reclaimed.work_item_id, error="final failure")
    assert updated.state == WorkItemState.FAILED
    assert updated.attempts == 3
    assert updated.completed_at is not None


# --- requeue_stale_running (general ADR-006 crash-recovery concern) ------------------------


def test_requeue_stale_running_recovers_a_crashed_items_state(session, storage):
    """A `running` Work Item with no code path back to `queued` (see `claim_next_queued`'s and
    `requeue_stale_running`'s own docstrings) models exactly what a process crash leaves behind:
    claimed, never completed. This is the general recovery mechanism found missing during
    Project Writing Stage 8 validation - not Writing-specific, tested here against a plain
    document-processing Work Item.
    """
    _upload_document(session, storage)
    work_items = WorkItemRepository(session)
    item = work_items.claim_next_queued()
    assert item.state == WorkItemState.RUNNING

    row = session.get(WorkItemModel, item.work_item_id)
    row.executed_at = row.executed_at - timedelta(hours=1)
    session.flush()

    recovered = work_items.requeue_stale_running(stale_after=timedelta(minutes=10))
    session.commit()

    assert recovered == 1
    row = session.get(WorkItemModel, item.work_item_id)
    assert row.state == WorkItemState.QUEUED
    assert row.attempts == 1
    assert "stale running" in row.last_error.lower()


def test_requeue_stale_running_ignores_recently_claimed_items(session, storage):
    """A `running` row claimed moments ago (the currently-executing item, in the real single-
    process executor) must never be touched - only a prior process's abandoned claim.
    """
    _upload_document(session, storage)
    work_items = WorkItemRepository(session)
    item = work_items.claim_next_queued()

    recovered = work_items.requeue_stale_running(stale_after=timedelta(minutes=10))

    assert recovered == 0
    row = session.get(WorkItemModel, item.work_item_id)
    assert row.state == WorkItemState.RUNNING


def test_requeue_stale_running_terminates_a_poison_item_once_attempts_are_exhausted(session, storage):
    _upload_document(session, storage)
    work_items = WorkItemRepository(session)
    item = work_items.claim_next_queued()
    row = session.get(WorkItemModel, item.work_item_id)
    row.attempts = 2  # one recovery away from DEFAULT_MAX_ATTEMPTS (3)
    row.executed_at = row.executed_at - timedelta(hours=1)
    session.flush()

    recovered = work_items.requeue_stale_running(stale_after=timedelta(minutes=10))
    session.commit()

    assert recovered == 1
    row = session.get(WorkItemModel, item.work_item_id)
    assert row.state == WorkItemState.FAILED
    assert row.attempts == 3
    assert row.completed_at is not None


def test_requeue_stale_running_ignores_non_running_states(session, storage):
    _upload_document(session, storage)
    work_items = WorkItemRepository(session)
    assert work_items.requeue_stale_running(stale_after=timedelta(minutes=10)) == 0  # still queued


def test_executor_loop_start_recovers_stale_running_items_before_polling(session_factory, storage):
    """End-to-end proof that `WorkItemExecutorLoop.start()` actually calls the recovery hook
    (not just that the repository method works in isolation): a stale `running` row present at
    startup is queued again and then genuinely processed to completion.
    """
    session = session_factory()
    try:
        document_id = _upload_document(session, storage)
        work_items = WorkItemRepository(session)
        item = work_items.claim_next_queued()
        row = session.get(WorkItemModel, item.work_item_id)
        row.executed_at = row.executed_at - timedelta(hours=1)
        session.commit()
    finally:
        session.close()

    provider = FakeTextGenerationProvider(
        responses=['{"element_type": "concept", "label": "Recovered", "description": "d"}']
    )
    loop = WorkItemExecutorLoop(
        session_factory,
        provider,
        FakeEmbeddingProvider(),
        "test-embedding-model",
        storage,
        poll_interval=0.05,
        stale_running_threshold=timedelta(minutes=10),
    )

    async def _drive() -> None:
        loop.start()
        for _ in range(50):
            await asyncio.sleep(0.05)
            check = session_factory()
            try:
                doc = check.get(ResearchDocument, document_id)
                if doc.processing_status == DocumentProcessingStatus.PROCESSED:
                    break
            finally:
                check.close()
        await loop.stop()

    asyncio.run(_drive())

    verify = session_factory()
    try:
        doc = verify.get(ResearchDocument, document_id)
        assert doc.processing_status == DocumentProcessingStatus.PROCESSED
    finally:
        verify.close()


# --- process_one_work_item, end to end ----------------------------------------------------


def test_process_one_work_item_returns_false_on_an_empty_queue(session, storage):
    provider = FakeTextGenerationProvider()
    assert _process_one(session, storage, text_provider=provider) is False


def test_process_one_work_item_succeeds_and_transitions_document_to_processed(session, storage):
    document_id = _upload_document(
        session, storage, content=b"Paragraph one.\n\nParagraph two.")
    provider = FakeTextGenerationProvider(
        responses=[
            '{"element_type": "theme", "label": "Overview", "description": "d"}']
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
    # the item is now succeeded, not queued
    assert work_items.claim_next_queued() is None


def test_process_one_work_item_embedding_failure_requeues_like_any_other_pipeline_failure(session, storage):
    document_id = _upload_document(session, storage)
    provider = FakeTextGenerationProvider()
    embedding_provider = FakeEmbeddingProvider(always_fail=True)

    _process_one(session, storage, text_provider=provider,
                 embedding_provider=embedding_provider)

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
    # requeued, not yet exhausted
    assert document.processing_status == DocumentProcessingStatus.PENDING

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


def test_process_one_writing_work_item_generates_version_and_succeeds(session, storage):
    draft_id, chunk_id, request_id, _message_id = _enqueue_writing_generation(
        session, storage, request_id="writing-success")
    provider = FakeTextGenerationProvider(responses=["Generated writing."])

    assert _process_one(session, storage, text_provider=provider) is True

    versions = SqlAlchemyDraftVersionRepository(
        session).list_by_draft_id(draft_id)
    assert len(versions) == 1
    assert versions[0].content == "Generated writing."
    links = session.query(DraftEvidenceLink).all()
    assert len(links) == 1
    assert links[0].chunk_id == chunk_id
    assert WorkItemRepository(session).claim_next_queued() is None
    assert provider.call_count == 1
    succeeded = session.query(WorkItemModel).filter_by(idempotency_key=f"generate_draft_version:{request_id}").one()
    assert succeeded.state == WorkItemState.SUCCEEDED
    assert succeeded.attempts == 0
    assert succeeded.completed_at is not None


def test_process_one_writing_work_item_links_instructions_message_to_generated_version(session, storage):
    """Resolves the instructions-contract discrepancy: once generation succeeds, the executor
    must link the instructions Message to the Draft Version it produced (Message Context Link)
    and record the system's own response as a second Message in the same Conversation.
    """
    from app.modules.writing.infrastructure.models import MessageContextLink as MessageContextLinkModel
    from app.modules.writing.infrastructure.models import Message as MessageModel

    draft_id, _chunk_id, _request_id, message_id = _enqueue_writing_generation(
        session, storage, request_id="writing-with-message", with_instructions_message=True
    )
    provider = FakeTextGenerationProvider(responses=["Generated writing."])

    assert _process_one(session, storage, text_provider=provider) is True

    version = SqlAlchemyDraftVersionRepository(session).list_by_draft_id(draft_id)[0]
    conversation_id = session.get(MessageModel, message_id).conversation_id
    conversation_messages = session.query(MessageModel).filter_by(conversation_id=conversation_id).all()
    assert len(conversation_messages) == 2  # the instructions message and the system's response

    response_message = next(m for m in conversation_messages if m.message_id != message_id)
    assert response_message.direction.value == "system_response"
    assert str(version.version_number) in response_message.content

    links = session.query(MessageContextLinkModel).all()
    assert {link.message_id for link in links} == {message_id, response_message.message_id}
    assert all(link.draft_version_id == version.version_id for link in links)


def test_process_one_writing_failure_retries_and_preserves_atomicity(session, storage):
    draft_id, _, _, _ = _enqueue_writing_generation(
        session, storage, request_id="writing-failure")
    provider = FakeTextGenerationProvider(always_fail=True)

    for attempt in range(3):
        assert _process_one(session, storage, text_provider=provider) is True

    assert SqlAlchemyDraftVersionRepository(
        session).list_by_draft_id(draft_id) == []
    assert WorkItemRepository(session).claim_next_queued() is None
    failed = session.query(WorkItemModel).filter_by(idempotency_key="generate_draft_version:writing-failure").one()
    assert failed.state == WorkItemState.FAILED
    assert failed.attempts == 3
    assert failed.completed_at is not None
