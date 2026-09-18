"""Real-SQLite integration coverage for ResetAgentWorkspaceUseCase - the single most
destructive, cross-cutting operation in the codebase. SQLite foreign keys are enforced
(app/database/base.py), so this proves the deletion order is actually correct, not just that
it compiles: every agent-scoped table is populated, the reset is run, and every single row is
confirmed gone with no FK violation - plus that a fresh onboarding works immediately after, and
that a second agent's data is completely untouched.
"""

import pytest
from sqlalchemy import text

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.reset_workspace import ResetAgentWorkspaceUseCase
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.infrastructure.models import ResearchDocument as ResearchDocumentModel
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.domain.enums import CreatedBy as KnowledgeCreatedBy
from app.modules.knowledge.domain.enums import KnowledgeElementType
from app.modules.knowledge.infrastructure.models import ChunkEvidenceLink, KnowledgeChunk, KnowledgeElement
from app.modules.knowledge.infrastructure.vector_models import KnowledgeChunkEmbedding
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.application.chat import StartConversationUseCase
from app.modules.writing.application.style_extraction import ExtractWritingStyleProfileUseCase
from app.modules.writing.application.style_ingestion import UploadWritingStyleDocumentUseCase
from app.modules.writing.domain.entities import MemoryProvenanceLink, MemoryRecord, Message, MessageContextLink
from app.modules.writing.domain.enums import MemoryProvenanceSourceType, MemoryRecordType, MessageContextTargetType, MessageDirection
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMemoryProvenanceLinkRepository,
    SqlAlchemyMemoryRecordRepository,
    SqlAlchemyMessageContextLinkRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyProfileCharacteristicRepository,
    SqlAlchemyProfileCharacteristicSourceRepository,
    SqlAlchemyWritingProfileRepository,
)
from app.storage.filesystem import FilesystemStorage

# Every table this reset touches, with the SQL to count rows belonging to one agent - each
# mirrors the scoping subquery chain the use case's own DELETE statements use.
_COUNT_QUERIES = {
    "writing_profiles": "SELECT COUNT(*) FROM writing_profiles WHERE agent_id = :a",
    "memory_records": "SELECT COUNT(*) FROM memory_records WHERE agent_id = :a",
    "conversations": "SELECT COUNT(*) FROM conversations WHERE agent_id = :a",
    "knowledge_elements": "SELECT COUNT(*) FROM knowledge_elements WHERE agent_id = :a",
    "knowledge_chunks": "SELECT COUNT(*) FROM knowledge_chunks WHERE agent_id = :a",
    "projects": "SELECT COUNT(*) FROM projects WHERE agent_id = :a",
    "research_documents": (
        "SELECT COUNT(*) FROM research_documents WHERE project_id IN "
        "(SELECT project_id FROM projects WHERE agent_id = :a)"
    ),
    "profile_characteristics": (
        "SELECT COUNT(*) FROM profile_characteristics WHERE profile_id IN "
        "(SELECT profile_id FROM writing_profiles WHERE agent_id = :a)"
    ),
    "profile_characteristic_sources": (
        "SELECT COUNT(*) FROM profile_characteristic_sources WHERE characteristic_id IN "
        "(SELECT characteristic_id FROM profile_characteristics WHERE profile_id IN "
        "(SELECT profile_id FROM writing_profiles WHERE agent_id = :a))"
    ),
    "memory_provenance_links": (
        "SELECT COUNT(*) FROM memory_provenance_links WHERE record_id IN "
        "(SELECT record_id FROM memory_records WHERE agent_id = :a)"
    ),
    "messages": (
        "SELECT COUNT(*) FROM messages WHERE conversation_id IN "
        "(SELECT conversation_id FROM conversations WHERE agent_id = :a)"
    ),
    "message_context_links": (
        "SELECT COUNT(*) FROM message_context_links WHERE message_id IN (SELECT message_id FROM messages "
        "WHERE conversation_id IN (SELECT conversation_id FROM conversations WHERE agent_id = :a))"
    ),
    "chunk_evidence_links": (
        "SELECT COUNT(*) FROM chunk_evidence_links WHERE chunk_id IN "
        "(SELECT chunk_id FROM knowledge_chunks WHERE agent_id = :a)"
    ),
    "knowledge_chunk_embeddings": (
        "SELECT COUNT(*) FROM knowledge_chunk_embeddings WHERE chunk_id IN "
        "(SELECT chunk_id FROM knowledge_chunks WHERE agent_id = :a)"
    ),
    "knowledge_chunk_fts": "SELECT COUNT(*) FROM knowledge_chunk_fts WHERE agent_id = :a",
}


class FakeTextGenerationProviderForStyle:
    def generate(self, prompt: str) -> str:
        return '{"characteristics": [{"characteristic_type": "structure", "signal": "Short sentences.", "confidence": 0.8}]}'


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "reset_workspace_test.db"
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


def _fully_populate_a_workspace(session, storage, *, username: str) -> tuple[int, int]:
    """Creates a real user + agent + project, then populates every single agent-scoped table
    in the reset's deletion list via the real use cases (and a couple of direct model/
    repository inserts where no use case exists, or where exercising the real chat-triggered
    Memory pipeline would need 20 real messages) - a real Writing Profile/Characteristic/
    Source, a real Memory Record/Provenance Link, a real Conversation/Message/Message Context
    Link, and real Knowledge Element/Chunk/Embedding/Evidence Link. Returns (user_id,
    agent_id).
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
    agent_id = workspace.agent.agent_id

    # Knowledge: a processed research document with a real element/chunk/embedding/evidence link.
    document = ResearchDocumentModel(
        project_id=workspace.project.project_id, title="Doc", format="txt", content_reference="ref-1"
    )
    session.add(document)
    session.flush()
    element = KnowledgeElement(
        agent_id=agent_id, element_type=KnowledgeElementType.CONCEPT,
        label="Concept", created_by=KnowledgeCreatedBy.SYSTEM,
    )
    session.add(element)
    session.flush()
    chunk = KnowledgeChunk(agent_id=agent_id, element_id=element.element_id, content="Chunk content.")
    session.add(chunk)
    session.flush()
    session.add(
        ChunkEvidenceLink(chunk_id=chunk.chunk_id, document_id=document.document_id, created_by=KnowledgeCreatedBy.SYSTEM)
    )
    session.add(
        KnowledgeChunkEmbedding(chunk_id=chunk.chunk_id, embedding_vector="[0.1, 0.2]", embedding_model_version="test")
    )
    session.flush()
    session.execute(
        text("INSERT INTO knowledge_chunk_fts(rowid, content, agent_id) VALUES (:rowid, :content, :agent_id)"),
        {"rowid": chunk.chunk_id, "content": chunk.content, "agent_id": agent_id},
    )

    # Conversation + Message, ahead of Memory so its Provenance Link can reference a real one.
    conversation = StartConversationUseCase(
        SqlAlchemyConversationRepository(session), agents, uow
    ).execute(user_id=user.user_id, title="Chat")
    message = SqlAlchemyMessageRepository(session).add(
        Message(
            conversation_id=conversation.conversation_id, sequence=1, direction=MessageDirection.USER_REQUEST,
            content="Hello.",
        )
    )
    session.commit()

    # Memory Record + Provenance Link. Chat is Memory's only real trigger (every
    # memory_extraction.MEMORY_EXTRACTION_TRIGGER_COUNT messages) - inserted directly here
    # rather than via 20 real chat turns, mirroring this fixture's existing "a couple of direct
    # inserts where no cheap use case exists" precedent (see module docstring).
    memory_records = SqlAlchemyMemoryRecordRepository(session)
    record = memory_records.add(
        MemoryRecord(agent_id=agent_id, record_type=MemoryRecordType.DECISION, content="A memory.")
    )
    session.commit()
    SqlAlchemyMemoryProvenanceLinkRepository(session).add(
        MemoryProvenanceLink(
            record_id=record.record_id,
            source_type=MemoryProvenanceSourceType.CONVERSATION,
            conversation_id=conversation.conversation_id,
        )
    )
    session.commit()

    # Writing Profile (created on first style upload) + Characteristic + Source (from a real
    # extraction run, using a fake provider - no real AI call needed for this fixture).
    style_upload = UploadWritingStyleDocumentUseCase(
        SqlAlchemyDocumentRepository(session), projects, agents, SqlAlchemyWritingProfileRepository(session),
        storage, uow,
    ).execute(user_id=user.user_id, title="Style sample", format="txt", content=b"Sample writing.", extension="txt")
    ExtractWritingStyleProfileUseCase(
        agents, projects, SqlAlchemyDocumentRepository(session), storage,
        SqlAlchemyWritingProfileRepository(session), SqlAlchemyProfileCharacteristicRepository(session),
        SqlAlchemyProfileCharacteristicSourceRepository(session), FakeTextGenerationProviderForStyle(), uow,
    ).execute(user_id=user.user_id, document_ids=[style_upload.document.document_id])

    # Message Context Link, linking the earlier message to the Memory Record it produced.
    SqlAlchemyMessageContextLinkRepository(session).add(
        MessageContextLink(
            message_id=message.message_id, target_type=MessageContextTargetType.MEMORY_RECORD,
            memory_record_id=record.record_id,
        )
    )
    session.commit()

    return user.user_id, agent_id


def _count(session, table: str, agent_id: int) -> int:
    return session.execute(text(_COUNT_QUERIES[table]), {"a": agent_id}).scalar()


def test_reset_deletes_every_agent_scoped_row_with_no_fk_violation(session, storage):
    user_id, agent_id = _fully_populate_a_workspace(session, storage, username="researcher")

    # Sanity: every table actually has at least one real row before the reset.
    for table in _COUNT_QUERIES:
        assert _count(session, table, agent_id) > 0, f"fixture did not populate {table}"

    ResetAgentWorkspaceUseCase(
        SqlAlchemyAgentRepository(session), session, SqlAlchemyUnitOfWork(session)
    ).execute(user_id=user_id)

    session.expire_all()
    assert SqlAlchemyAgentRepository(session).get_by_user_id(user_id) is None
    for table in _COUNT_QUERIES:
        assert _count(session, table, agent_id) == 0, f"{table} still has rows after reset"


def test_a_fresh_onboarding_works_immediately_after_reset(session, storage):
    user_id, _agent_id = _fully_populate_a_workspace(session, storage, username="researcher")
    ResetAgentWorkspaceUseCase(
        SqlAlchemyAgentRepository(session), session, SqlAlchemyUnitOfWork(session)
    ).execute(user_id=user_id)

    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    new_workspace = CreateAgentWorkspaceUseCase(
        agents, CreateProjectUseCase(projects), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=user_id, project_title="New Thesis", project_topic="A fresh start")

    assert new_workspace.project.topic == "A fresh start"
    assert agents.get_by_user_id(user_id) is not None


def test_reset_never_touches_a_different_agents_data(session, storage):
    user_a, agent_a = _fully_populate_a_workspace(session, storage, username="user-a")
    user_b, agent_b = _fully_populate_a_workspace(session, storage, username="user-b")

    ResetAgentWorkspaceUseCase(
        SqlAlchemyAgentRepository(session), session, SqlAlchemyUnitOfWork(session)
    ).execute(user_id=user_a)

    session.expire_all()
    assert SqlAlchemyAgentRepository(session).get_by_user_id(user_a) is None
    assert SqlAlchemyAgentRepository(session).get_by_user_id(user_b) is not None
    for table in _COUNT_QUERIES:
        assert _count(session, table, agent_a) == 0
        assert _count(session, table, agent_b) > 0, f"Agent B's {table} rows were wiped by resetting Agent A"


def test_a_new_chunk_created_after_reset_does_not_collide_with_an_orphaned_fts_row(session, storage):
    """Regression test for a real bug found 2026-09-18: knowledge_chunk_fts has no foreign key
    to knowledge_chunks, so it was never cleaned up by the reset - and SQLite reuses a deleted
    rowid the moment a table becomes fully empty (no AUTOINCREMENT on KnowledgeChunkModel), so
    the very next chunk created after a reset could land on the same chunk_id an orphaned FTS5
    row still held, failing the insert with a unique-constraint violation. Exercised via the
    real repository (not a raw insert) so this proves the actual write path, not just the SQL.
    """
    from app.modules.knowledge.domain.entities import KnowledgeChunk as KnowledgeChunkDomain
    from app.modules.knowledge.infrastructure.repositories import SqlAlchemyKnowledgeChunkRepository

    user_id, agent_id = _fully_populate_a_workspace(session, storage, username="researcher")
    first_chunk_id = session.execute(
        text("SELECT chunk_id FROM knowledge_chunks WHERE agent_id = :a"), {"a": agent_id}
    ).scalar()

    ResetAgentWorkspaceUseCase(
        SqlAlchemyAgentRepository(session), session, SqlAlchemyUnitOfWork(session)
    ).execute(user_id=user_id)
    session.expire_all()
    assert session.execute(text("SELECT COUNT(*) FROM knowledge_chunks")).scalar() == 0

    # A fresh workspace, then a new chunk - real SQLite behavior reuses first_chunk_id here.
    agents = SqlAlchemyAgentRepository(session)
    new_workspace = CreateAgentWorkspaceUseCase(
        agents, CreateProjectUseCase(SqlAlchemyProjectRepository(session)), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=user_id, project_title="New Thesis", project_topic="A fresh start")
    new_element = KnowledgeElement(
        agent_id=new_workspace.agent.agent_id, element_type=KnowledgeElementType.CONCEPT,
        label="Concept", created_by=KnowledgeCreatedBy.SYSTEM,
    )
    session.add(new_element)
    session.flush()

    new_chunk = SqlAlchemyKnowledgeChunkRepository(session).add(
        KnowledgeChunkDomain(
            chunk_id=None, agent_id=new_workspace.agent.agent_id, element_id=new_element.element_id,
            content="Reused-id chunk.",
        )
    )
    session.commit()  # must not raise a unique-constraint violation

    assert new_chunk.chunk_id == first_chunk_id  # confirms the id genuinely was reused, not a coincidence-free pass


def test_resetting_a_user_with_no_agent_is_rejected(session):
    user = User(username="no-agent")
    session.add(user)
    session.flush()

    with pytest.raises(AgentNotFoundForUserError):
        ResetAgentWorkspaceUseCase(
            SqlAlchemyAgentRepository(session), session, SqlAlchemyUnitOfWork(session)
        ).execute(user_id=user.user_id)
