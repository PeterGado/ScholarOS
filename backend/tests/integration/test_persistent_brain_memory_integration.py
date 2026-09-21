"""Real-SQLite integration coverage for the Persistent Brain Memory write path, now that its
only trigger is chat itself (the Drafts/Review pipeline this used to ride on - Persistent
Brain Decision 4 - was removed entirely): a conversation that grows past
`memory_extraction.MEMORY_EXTRACTION_TRIGGER_COUNT` real messages, processed through the real
async Work Item executor, must produce Memory Records with CONVERSATION provenance - and must
never leak across Agents, and never fail the chat reply itself.
"""

import logging

import pytest

from app.ai.usage_guard import AiUsageGuard
from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.application.retrieval import SearchKnowledgeUseCase
from app.modules.knowledge.infrastructure.repositories import (
    SqlAlchemyChunkEvidenceLinkRepository,
    SqlAlchemyKnowledgeChunkEmbeddingRepository,
    SqlAlchemyKnowledgeChunkRepository,
    SqlAlchemyLexicalSearchRepository,
)
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.application.chat import SendChatMessageUseCase, StartConversationUseCase
from app.modules.writing.domain.enums import MemoryProvenanceSourceType
from app.modules.writing.domain.memory_extraction import MEMORY_EXTRACTION_TRIGGER_COUNT
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMemoryProvenanceLinkRepository,
    SqlAlchemyMemoryRecordRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyProfileCharacteristicRepository,
    SqlAlchemyWritingProfileRepository,
)
from app.storage.filesystem import FilesystemStorage
from app.workers.executor import process_one_work_item
from app.workers.repository import WorkItemRepository


class FakeTextGenerationProvider:
    def __init__(self, *, reply="A reply.", memory_response=None):
        self._reply = reply
        self._memory_response = memory_response or (
            '{"memories": [{"record_type": "decision", "content": "Use LIDAR survey data.", "rationale": ""}]}'
        )
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        if "compacting an ongoing conversation" in prompt:
            return "A rolling summary."
        if "extracting durable project memory" in prompt:
            return self._memory_response
        return self._reply


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        return [0.0, 0.0]


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "persistent_brain_memory_test.db"
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


def _make_workspace(session, *, username, topic="Topic", description=None):
    user = User(username=username)
    session.add(user)
    session.flush()
    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    workspace = CreateAgentWorkspaceUseCase(agents, CreateProjectUseCase(projects), uow).execute(
        user_id=user.user_id, project_title="Thesis", project_topic=topic
    )
    if description is not None:
        from app.modules.project.infrastructure.models import Project as ProjectModel

        row = session.get(ProjectModel, workspace.project.project_id)
        row.description = description
        session.flush()
        session.commit()
    else:
        session.commit()
    return workspace


def _search_knowledge_use_case(session) -> SearchKnowledgeUseCase:
    return SearchKnowledgeUseCase(
        SqlAlchemyAgentRepository(session),
        FakeEmbeddingProvider(),
        SqlAlchemyKnowledgeChunkEmbeddingRepository(session),
        SqlAlchemyKnowledgeChunkRepository(session),
        SqlAlchemyChunkEvidenceLinkRepository(session),
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyLexicalSearchRepository(session),
        AiUsageGuard(None, None, daily_token_cap=None),
    )


def _send_and_process(session, storage, workspace, conversation_id, content, provider):
    use_case = SendChatMessageUseCase(
        SqlAlchemyConversationRepository(session),
        SqlAlchemyMessageRepository(session),
        SqlAlchemyAgentRepository(session),
        SqlAlchemyProjectRepository(session),
        SqlAlchemyWritingProfileRepository(session),
        SqlAlchemyProfileCharacteristicRepository(session),
        SqlAlchemyMemoryRecordRepository(session),
        _search_knowledge_use_case(session),
        WorkItemRepository(session),
        storage,
        SqlAlchemyUnitOfWork(session),
        AiUsageGuard(None, None, daily_token_cap=None),
    )
    use_case.execute(user_id=workspace.agent.user_id, conversation_id=conversation_id, content=content)
    assert process_one_work_item(
        session,
        text_provider=provider,
        embedding_provider=FakeEmbeddingProvider(),
        embedding_model_version="test-embedding-model",
        storage=storage,
    ) is True


def _start_conversation(session, workspace):
    return StartConversationUseCase(
        SqlAlchemyConversationRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=workspace.agent.user_id)


def test_a_conversation_that_reaches_the_trigger_count_produces_a_memory_record_with_conversation_provenance(
    session, storage
):
    workspace = _make_workspace(session, username="researcher", topic="Erosion on barrier islands")
    conversation = _start_conversation(session, workspace)
    provider = FakeTextGenerationProvider(
        memory_response='{"memories": [{"record_type": "decision", "content": "Use LIDAR survey data.", "rationale": "From chat."}]}'
    )

    # MEMORY_EXTRACTION_TRIGGER_COUNT/2 send/reply cycles = exactly MEMORY_EXTRACTION_TRIGGER_COUNT real messages.
    for i in range(MEMORY_EXTRACTION_TRIGGER_COUNT // 2):
        _send_and_process(session, storage, workspace, conversation.conversation_id, f"Message {i}.", provider)

    records = SqlAlchemyMemoryRecordRepository(session).list_current_by_agent_id(workspace.agent.agent_id)
    assert len(records) == 1
    assert records[0].content == "Use LIDAR survey data."
    assert records[0].agent_id == workspace.agent.agent_id

    provenance = SqlAlchemyMemoryProvenanceLinkRepository(session).list_by_record_id(records[0].record_id)
    assert len(provenance) == 1
    assert provenance[0].source_type == MemoryProvenanceSourceType.CONVERSATION
    assert provenance[0].conversation_id == conversation.conversation_id


def test_memory_is_not_extracted_before_the_trigger_count_is_reached(session, storage):
    workspace = _make_workspace(session, username="researcher")
    conversation = _start_conversation(session, workspace)
    provider = FakeTextGenerationProvider()

    for i in range(MEMORY_EXTRACTION_TRIGGER_COUNT // 2 - 1):
        _send_and_process(session, storage, workspace, conversation.conversation_id, f"Message {i}.", provider)

    assert SqlAlchemyMemoryRecordRepository(session).list_current_by_agent_id(workspace.agent.agent_id) == []


def test_a_malformed_memory_extraction_response_does_not_fail_the_chat_reply(session, storage, caplog):
    """Mirrors conversation summarization's own swallow-failure discipline
    (GenerateConversationReplyUseCase._extract_memory_if_needed's docstring): a bad extraction
    must never turn an otherwise-successful chat reply into a failed Work Item - but (2026-09-21
    security pass) it must also not vanish without a trace; a warning is logged.
    """
    workspace = _make_workspace(session, username="researcher")
    conversation = _start_conversation(session, workspace)
    provider = FakeTextGenerationProvider(memory_response="not valid json")

    with caplog.at_level(logging.WARNING, logger="app.modules.writing.application.chat"):
        for i in range(MEMORY_EXTRACTION_TRIGGER_COUNT // 2):
            _send_and_process(session, storage, workspace, conversation.conversation_id, f"Message {i}.", provider)

    messages = SqlAlchemyMessageRepository(session).list_by_conversation_id(conversation.conversation_id)
    assert len(messages) == MEMORY_EXTRACTION_TRIGGER_COUNT  # every reply still persisted successfully
    assert SqlAlchemyMemoryRecordRepository(session).list_current_by_agent_id(workspace.agent.agent_id) == []
    assert WorkItemRepository(session).claim_next_queued() is None  # no failed/requeued work item left behind
    assert any("Memory extraction failed" in record.message for record in caplog.records)


def test_memory_records_and_provenance_do_not_leak_across_agents(session, storage):
    """The mandatory cross-agent isolation test (Persistent Brain §15/§17): Agent A's chat
    history must never produce or expose memory visible to Agent B, and vice versa.
    """
    workspace_a = _make_workspace(session, username="user-a", topic="Topic A", description="Description A.")
    workspace_b = _make_workspace(session, username="user-b", topic="Topic B", description="Description B.")
    conversation_a = _start_conversation(session, workspace_a)
    conversation_b = _start_conversation(session, workspace_b)

    provider_a = FakeTextGenerationProvider(
        memory_response='{"memories": [{"record_type": "decision", "content": "Memory from agent A.", "rationale": ""}]}'
    )
    for i in range(MEMORY_EXTRACTION_TRIGGER_COUNT // 2):
        _send_and_process(session, storage, workspace_a, conversation_a.conversation_id, f"A message {i}.", provider_a)

    provider_b = FakeTextGenerationProvider(
        memory_response='{"memories": [{"record_type": "decision", "content": "Memory from agent B.", "rationale": ""}]}'
    )
    for i in range(MEMORY_EXTRACTION_TRIGGER_COUNT // 2):
        _send_and_process(session, storage, workspace_b, conversation_b.conversation_id, f"B message {i}.", provider_b)

    records = SqlAlchemyMemoryRecordRepository(session)
    a_records = records.list_current_by_agent_id(workspace_a.agent.agent_id)
    b_records = records.list_current_by_agent_id(workspace_b.agent.agent_id)

    assert [r.content for r in a_records] == ["Memory from agent A."]
    assert [r.content for r in b_records] == ["Memory from agent B."]

    provenance = SqlAlchemyMemoryProvenanceLinkRepository(session)
    a_provenance = provenance.list_by_record_id(a_records[0].record_id)
    assert a_provenance[0].conversation_id == conversation_a.conversation_id
    assert a_provenance[0].conversation_id != conversation_b.conversation_id
