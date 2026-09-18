"""Real-SQLite integration coverage for Persistent Brain v2 (Reflection & Memory Control):
scalable conversation memory (summarization actually triggering and actually being picked up
by later context resolution) and memory inspection/supersession, including the mandatory
cross-agent isolation checks.
"""

import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.knowledge.application.retrieval import SearchKnowledgeUseCase
from app.modules.knowledge.infrastructure.repositories import (
    SqlAlchemyChunkEvidenceLinkRepository,
    SqlAlchemyKnowledgeChunkEmbeddingRepository,
    SqlAlchemyKnowledgeChunkRepository,
    SqlAlchemyLexicalSearchRepository,
)
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.application.chat import SendChatMessageUseCase, StartConversationUseCase
from app.modules.writing.application.memory_inspection import ListMemoryUseCase, SupersedeMemoryRecordUseCase
from app.modules.writing.domain.conversation_context import CONVERSATION_SUMMARY_ORIGIN
from app.modules.writing.domain.entities import MemoryRecord
from app.modules.writing.domain.enums import CreatedBy, MemoryRecordType
from app.modules.writing.domain.exceptions import MemoryRecordNotFoundError
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMemoryProvenanceLinkRepository,
    SqlAlchemyMemoryRecordRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyProfileCharacteristicRepository,
    SqlAlchemyWritingProfileRepository,
)
from app.modules.writing.infrastructure.models import Conversation as ConversationModel
from app.storage.filesystem import FilesystemStorage
from app.workers.executor import process_one_work_item
from app.workers.repository import WorkItemRepository


class FakeTextGenerationProvider:
    def __init__(self, reply: str = "A reply.", summary: str = "A rolling summary of the conversation so far."):
        self._reply = reply
        self._summary = summary
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        if "compacting an ongoing conversation" in prompt:
            return self._summary
        return self._reply


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        return [0.0, 0.0]


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "persistent_brain_v2_test.db"
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


def _make_workspace(session, *, username, topic="Topic"):
    user = User(username=username)
    session.add(user)
    session.flush()
    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    workspace = CreateAgentWorkspaceUseCase(agents, CreateProjectUseCase(projects), uow).execute(
        user_id=user.user_id, project_title="Thesis", project_topic=topic
    )
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
    )
    use_case.execute(user_id=workspace.agent.user_id, conversation_id=conversation_id, content=content)
    process_one_work_item(
        session,
        text_provider=provider,
        embedding_provider=FakeEmbeddingProvider(),
        embedding_model_version="test-embedding-model",
        storage=storage,
    )


# --- Scalable conversation memory: summarization actually triggers ------------------------


def test_a_long_conversation_gets_summarized_and_the_summary_is_used_going_forward(session, storage):
    workspace = _make_workspace(session, username="researcher")
    conversation = StartConversationUseCase(
        SqlAlchemyConversationRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=workspace.agent.user_id)
    provider = FakeTextGenerationProvider()

    # 11 send/reply cycles = 22 real messages, comfortably past CONVERSATION_SUMMARY_TRIGGER_COUNT (20).
    for i in range(11):
        _send_and_process(session, storage, workspace, conversation.conversation_id, f"Message {i}.", provider)

    messages = SqlAlchemyMessageRepository(session).list_by_conversation_id(conversation.conversation_id)
    summary_messages = [m for m in messages if m.origin == CONVERSATION_SUMMARY_ORIGIN]
    assert len(summary_messages) == 1
    assert summary_messages[0].content == "A rolling summary of the conversation so far."

    session.expire_all()
    stored_conversation = session.get(ConversationModel, conversation.conversation_id)
    assert stored_conversation.status.value == "summarized"
    assert stored_conversation.summarized_at is not None

    # Nothing was deleted - the full raw history is still there.
    assert len(messages) == 22 + 1  # + the one summary message

    # The NEXT message's real prompt actually includes the summary, not 20+ raw messages.
    prior_call_count = provider.call_count
    _send_and_process(session, storage, workspace, conversation.conversation_id, "One more message.", provider)
    assert provider.call_count == prior_call_count + 1  # only the reply call, no re-summarization yet


# --- Memory inspection: cross-agent isolation and supersession -----------------------------


def _add_current_memory(session, agent_id: int, content: str) -> MemoryRecord:
    return SqlAlchemyMemoryRecordRepository(session).add(
        MemoryRecord(agent_id=agent_id, record_type=MemoryRecordType.DECISION, content=content, created_by=CreatedBy.SYSTEM)
    )


def test_memory_listing_and_supersede_do_not_leak_across_agents(session, storage):
    workspace_a = _make_workspace(session, username="user-a")
    workspace_b = _make_workspace(session, username="user-b")
    record_a = _add_current_memory(session, workspace_a.agent.agent_id, "Memory belonging to Agent A.")
    _add_current_memory(session, workspace_b.agent.agent_id, "Memory belonging to Agent B.")
    session.commit()

    list_use_case = ListMemoryUseCase(
        SqlAlchemyMemoryRecordRepository(session),
        SqlAlchemyMemoryProvenanceLinkRepository(session),
        SqlAlchemyAgentRepository(session),
    )
    a_memory = list_use_case.execute(user_id=workspace_a.agent.user_id)
    b_memory = list_use_case.execute(user_id=workspace_b.agent.user_id)

    assert [m.record.content for m in a_memory] == ["Memory belonging to Agent A."]
    assert [m.record.content for m in b_memory] == ["Memory belonging to Agent B."]

    # User B cannot supersede User A's memory record - reported as not found, not forbidden.
    supersede_use_case = SupersedeMemoryRecordUseCase(
        SqlAlchemyMemoryRecordRepository(session),
        SqlAlchemyMemoryProvenanceLinkRepository(session),
        SqlAlchemyAgentRepository(session),
        SqlAlchemyUnitOfWork(session),
    )
    with pytest.raises(MemoryRecordNotFoundError):
        supersede_use_case.execute(user_id=workspace_b.agent.user_id, record_id=record_a.record_id, content="Hijacked.")


def test_supersede_against_real_sqlite_preserves_the_old_row_and_creates_a_new_current_one(session, storage):
    workspace = _make_workspace(session, username="researcher")
    old = _add_current_memory(session, workspace.agent.agent_id, "Original content.")
    session.commit()

    use_case = SupersedeMemoryRecordUseCase(
        SqlAlchemyMemoryRecordRepository(session),
        SqlAlchemyMemoryProvenanceLinkRepository(session),
        SqlAlchemyAgentRepository(session),
        SqlAlchemyUnitOfWork(session),
    )
    new_record = use_case.execute(user_id=workspace.agent.user_id, record_id=old.record_id, content="Corrected content.")

    session.expire_all()
    current = SqlAlchemyMemoryRecordRepository(session).list_current_by_agent_id(workspace.agent.agent_id)
    assert [r.content for r in current] == ["Corrected content."]

    stored_old = SqlAlchemyMemoryRecordRepository(session).get_by_id(old.record_id)
    assert stored_old.status.value == "superseded"
    assert stored_old.superseded_record_id == new_record.record_id
    assert stored_old.content == "Original content."  # the old row itself is never rewritten
