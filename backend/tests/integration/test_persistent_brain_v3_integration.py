"""Real-SQLite integration coverage for the Persistent Brain v3 audit fixes: memory is now
ordered most-recent-first and bounded before reaching a prompt, and this is proven through the
*real* chat pipeline (SendChatMessageUseCase -> the real Work Item executor -> the real
assembled prompt) - not a hand-built ContextAssemblyInput, directly answering the audit's
"no end-to-end cognitive loop test" finding for the memory-bounding path.
"""

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
from app.modules.writing.domain.entities import MemoryRecord
from app.modules.writing.domain.enums import CreatedBy, MemoryRecordType
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMemoryRecordRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyProfileCharacteristicRepository,
    SqlAlchemyWritingProfileRepository,
)
from app.storage.filesystem import FilesystemStorage
from app.workers.executor import process_one_work_item
from app.workers.repository import WorkItemRepository


class SpyingTextGenerationProvider:
    def __init__(self, reply: str = "A reply.") -> None:
        self._reply = reply
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._reply


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        return [0.0, 0.0]


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "persistent_brain_v3_test.db"
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


def _make_workspace(session, *, username="researcher", topic="Topic"):
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


# --- Repository ordering ---------------------------------------------------------------------


def test_list_current_by_agent_id_is_ordered_most_recent_first(session, storage):
    workspace = _make_workspace(session)
    records = SqlAlchemyMemoryRecordRepository(session)
    for i in range(5):
        records.add(
            MemoryRecord(
                agent_id=workspace.agent.agent_id, record_type=MemoryRecordType.DECISION,
                content=f"Memory {i}.", created_by=CreatedBy.SYSTEM,
            )
        )
    session.commit()

    result = records.list_current_by_agent_id(workspace.agent.agent_id)

    assert [r.content for r in result] == ["Memory 4.", "Memory 3.", "Memory 2.", "Memory 1.", "Memory 0."]


# --- The real cognitive loop: bounded memory actually reaching a real assembled prompt -------


def test_only_the_most_recent_memories_reach_a_real_chat_prompt(session, storage):
    workspace = _make_workspace(session)
    memory_records = SqlAlchemyMemoryRecordRepository(session)
    for i in range(25):
        memory_records.add(
            MemoryRecord(
                agent_id=workspace.agent.agent_id, record_type=MemoryRecordType.DECISION,
                content=f"Memory number {i}.", created_by=CreatedBy.SYSTEM,
            )
        )
    session.commit()

    conversation = StartConversationUseCase(
        SqlAlchemyConversationRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=workspace.agent.user_id)

    search_knowledge = SearchKnowledgeUseCase(
        SqlAlchemyAgentRepository(session),
        FakeEmbeddingProvider(),
        SqlAlchemyKnowledgeChunkEmbeddingRepository(session),
        SqlAlchemyKnowledgeChunkRepository(session),
        SqlAlchemyChunkEvidenceLinkRepository(session),
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyLexicalSearchRepository(session),
        AiUsageGuard(None, None, daily_token_cap=None),
    )
    send_message = SendChatMessageUseCase(
        SqlAlchemyConversationRepository(session),
        SqlAlchemyMessageRepository(session),
        SqlAlchemyAgentRepository(session),
        SqlAlchemyProjectRepository(session),
        SqlAlchemyWritingProfileRepository(session),
        SqlAlchemyProfileCharacteristicRepository(session),
        memory_records,
        search_knowledge,
        WorkItemRepository(session),
        storage,
        SqlAlchemyUnitOfWork(session),
        AiUsageGuard(None, None, daily_token_cap=None),
    )
    send_message.execute(user_id=workspace.agent.user_id, conversation_id=conversation.conversation_id, content="Hello.")

    spy = SpyingTextGenerationProvider()
    claimed = process_one_work_item(
        session, text_provider=spy, embedding_provider=FakeEmbeddingProvider(),
        embedding_model_version="test-embedding-model", storage=storage,
    )
    assert claimed is True
    assert len(spy.prompts) == 1
    real_prompt = spy.prompts[0]

    # The 20 most recent memories (25, 24, ..., 5) reach the real prompt...
    assert "Memory number 24." in real_prompt
    assert "Memory number 5." in real_prompt
    # ...but the 5 oldest (0-4) are bounded out, exactly as DEFAULT_MAX_MEMORIES=20 intends.
    assert "Memory number 4." not in real_prompt
    assert "Memory number 0." not in real_prompt
