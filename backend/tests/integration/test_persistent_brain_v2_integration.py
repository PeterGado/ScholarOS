"""Real-SQLite integration coverage for Persistent Brain v2 (Reflection & Memory Control):
scalable conversation memory (summarization actually triggering and actually being picked up
by later context resolution) and memory inspection/supersession, including the mandatory
cross-agent isolation checks.
"""

import logging

import pytest

from app.ai.usage_guard import AiUsageGuard
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
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.application.chat import SendChatMessageUseCase, StartConversationUseCase
from app.modules.writing.application.memory_inspection import ListMemoryUseCase, SupersedeMemoryRecordUseCase
from app.modules.writing.domain.conversation_context import CONVERSATION_SUMMARY_ORIGIN
from app.modules.writing.domain.entities import MemoryRecord
from app.modules.writing.domain.enums import CreatedBy, MemoryRecordType, MessageDirection
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


class FailingSummaryProvider:
    """Simulates a real summarization failure (e.g. a transient AI provider outage) - raises
    only for the summarization prompt, so a preceding reply-generation call in the same test
    still succeeds, isolating the summarization failure specifically.
    """

    def generate(self, prompt: str) -> str:
        if "compacting an ongoing conversation" in prompt:
            raise RuntimeError("Simulated provider outage during summarization.")
        return "A reply."


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        return [0.0, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


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
        AiUsageGuard(None, None, daily_token_cap=None),
    )


class FakeKnowledgeExtractionProvider:
    def generate(self, prompt: str) -> str:
        return '[{"element_type": "concept", "label": "Board independence", "description": "d"}]'


def _provision_document_with_knowledge(
    session, storage, workspace, *, content: bytes, author: str | None = None, publication_year: int | None = None
) -> None:
    """Uploads a real research document and drains its processing Work Item through the real
    queue (process_one_work_item) - not a direct ExtractDocumentKnowledgeUseCase call, which
    would leave the Work Item UploadResearchDocumentUseCase enqueues stuck QUEUED, ready to be
    wrongly claimed by a *later* process_one_work_item call meant for a chat reply. Leaves the
    workspace's knowledge base populated with real chunks/evidence links, including whatever
    author/publication_year metadata was supplied here, so a later chat message can retrieve
    real (not hand-built) evidence.
    """
    documents = SqlAlchemyDocumentRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    UploadResearchDocumentUseCase(
        documents,
        SqlAlchemyProjectRepository(session),
        SqlAlchemyAgentRepository(session),
        storage,
        uow,
        WorkItemRepository(session),
        AiUsageGuard(None, None, daily_token_cap=None),
    ).execute(
        project_id=workspace.project.project_id,
        user_id=workspace.agent.user_id,
        title="Doc",
        format="txt",
        content=content,
        author=author,
        publication_year=publication_year,
    )

    claimed = process_one_work_item(
        session,
        text_provider=FakeKnowledgeExtractionProvider(),
        embedding_provider=FakeEmbeddingProvider(),
        embedding_model_version="test-embedding-model",
        storage=storage,
        background_knowledge_provider=lambda topic: None,
    )
    assert claimed is True, "fixture bug: no document-processing Work Item was queued"


def _send_and_process(session, storage, workspace, conversation_id, content, provider, *, enable_multi_pass_generation=True):
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
    process_one_work_item(
        session,
        text_provider=provider,
        embedding_provider=FakeEmbeddingProvider(),
        embedding_model_version="test-embedding-model",
        storage=storage,
        # Never make a real Wikipedia network call from a test (2026-09-30).
        background_knowledge_provider=lambda topic: None,
        enable_multi_pass_generation=enable_multi_pass_generation,
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
    # Multi-pass generation (2026-10-06) is enabled by default: one reply now costs 3 generate()
    # calls (draft, critique, revise), not 1 - no re-summarization yet either way.
    assert provider.call_count == prior_call_count + 3


class StagedTextGenerationProvider:
    """Distinguishes the draft/critique/revise calls of one reply by ordinal position within
    the reply cycle specifically (not raw call_count), since summarization/memory-extraction
    calls can interleave between reply cycles and must not shift the draft/critique/revise
    position - matched by their own existing prompt markers first, same as
    FakeTextGenerationProvider above.
    """

    def __init__(
        self,
        *,
        draft: str = "Draft reply.",
        critique: str = "Found an issue to fix.",
        revision: str = "Revised reply.",
        summary: str = "A rolling summary of the conversation so far.",
    ):
        self._draft = draft
        self._critique = critique
        self._revision = revision
        self._summary = summary
        self.call_count = 0
        self.reply_call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        if "compacting an ongoing conversation" in prompt:
            return self._summary
        if "extracting durable project memory" in prompt:
            return '{"memories": []}'
        self.reply_call_count += 1
        position = (self.reply_call_count - 1) % 3
        if position == 0:
            return self._draft
        if position == 1:
            return self._critique
        return self._revision


def test_multi_pass_generation_persists_the_revision_not_the_draft(session, storage):
    workspace = _make_workspace(session, username="researcher-multi-pass")
    conversation = StartConversationUseCase(
        SqlAlchemyConversationRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=workspace.agent.user_id)
    provider = StagedTextGenerationProvider()

    _send_and_process(session, storage, workspace, conversation.conversation_id, "Write it.", provider)

    messages = SqlAlchemyMessageRepository(session).list_by_conversation_id(conversation.conversation_id)
    reply = next(m for m in messages if m.direction == MessageDirection.SYSTEM_RESPONSE)
    assert reply.content == "Revised reply."
    assert provider.reply_call_count == 3


def test_disabling_multi_pass_persists_the_draft_with_exactly_one_call(session, storage):
    workspace = _make_workspace(session, username="researcher-single-pass")
    conversation = StartConversationUseCase(
        SqlAlchemyConversationRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=workspace.agent.user_id)
    provider = StagedTextGenerationProvider()

    _send_and_process(
        session, storage, workspace, conversation.conversation_id, "Write it.", provider,
        enable_multi_pass_generation=False,
    )

    messages = SqlAlchemyMessageRepository(session).list_by_conversation_id(conversation.conversation_id)
    reply = next(m for m in messages if m.direction == MessageDirection.SYSTEM_RESPONSE)
    assert reply.content == "Draft reply."
    assert provider.reply_call_count == 1


def test_a_failing_summarization_does_not_fail_the_chat_reply_but_is_logged(session, storage, caplog):
    """Mirrors the malformed-memory-extraction test's own swallow-failure discipline
    (GenerateConversationReplyUseCase._summarize_if_needed's docstring): a summarization
    failure (e.g. a transient AI provider outage) must never turn an otherwise-successful chat
    reply into a failed Work Item - but (2026-09-21 security pass) it must not vanish without a
    trace either; a warning is logged.
    """
    workspace = _make_workspace(session, username="researcher")
    conversation = StartConversationUseCase(
        SqlAlchemyConversationRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=workspace.agent.user_id)
    provider = FailingSummaryProvider()

    with caplog.at_level(logging.WARNING, logger="app.modules.writing.application.chat"):
        # 11 send/reply cycles = 22 real messages, comfortably past the summarization trigger
        # count (20) - same scale as the happy-path test above.
        for i in range(11):
            _send_and_process(session, storage, workspace, conversation.conversation_id, f"Message {i}.", provider)

    messages = SqlAlchemyMessageRepository(session).list_by_conversation_id(conversation.conversation_id)
    assert len(messages) == 22  # every reply still persisted successfully; no summary was added
    assert all(m.origin != CONVERSATION_SUMMARY_ORIGIN for m in messages)
    session.expire_all()
    stored_conversation = session.get(ConversationModel, conversation.conversation_id)
    assert stored_conversation.status.value != "summarized"  # the failed attempt was rolled back
    assert WorkItemRepository(session).claim_next_queued() is None  # no failed/requeued work item left behind
    assert any("Conversation summarization failed" in record.message for record in caplog.records)


# --- Citation-fabrication guard (real production defect, 2026-10-02) -----------------------
# A live reproduction against production confirmed that, with zero research evidence, a reply
# can still contain plausible-looking fabricated citations despite the GROUNDING RULES prompt
# instruction forbidding it. These tests exercise the programmatic backstop end to end: a real
# Work Item run through process_one_work_item, not just the pure detection function.


def test_a_reply_with_citation_like_patterns_gets_a_warning_when_no_evidence_exists(session, storage):
    workspace = _make_workspace(session, username="researcher-citations")
    conversation = StartConversationUseCase(
        SqlAlchemyConversationRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=workspace.agent.user_id)
    provider = FakeTextGenerationProvider(reply="Uadiale (2012) suggests board independence matters.")

    _send_and_process(session, storage, workspace, conversation.conversation_id, "Add citations please.", provider)

    messages = SqlAlchemyMessageRepository(session).list_by_conversation_id(conversation.conversation_id)
    reply = next(m for m in messages if m.origin == "FakeTextGenerationProvider")
    assert "ScholarOS notice" in reply.content
    assert "Uadiale (2012)" in reply.content  # the original reply is kept, not replaced


def test_a_reply_without_citation_like_patterns_gets_no_warning(session, storage):
    workspace = _make_workspace(session, username="researcher-no-citations")
    conversation = StartConversationUseCase(
        SqlAlchemyConversationRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=workspace.agent.user_id)
    provider = FakeTextGenerationProvider(reply="This is a plain reply with no author-year patterns.")

    _send_and_process(session, storage, workspace, conversation.conversation_id, "Write something.", provider)

    messages = SqlAlchemyMessageRepository(session).list_by_conversation_id(conversation.conversation_id)
    reply = next(m for m in messages if m.origin == "FakeTextGenerationProvider")
    assert "ScholarOS notice" not in reply.content


# --- Citation grounding: a reply's citations checked against real supplied evidence (2026-10-06) --
# Closes the gap the guard above leaves open: that one only ever fires when there is NO evidence
# at all. A citation can be just as fabricated when real evidence exists but the model cites an
# author/year that doesn't match any of it - exercised here through the real retrieval pipeline
# (a real uploaded, processed, and extracted document), not a hand-built ContextEvidence.


def test_a_reply_citing_the_real_sources_author_and_year_gets_no_warning(session, storage):
    workspace = _make_workspace(session, username="researcher-real-citation")
    _provision_document_with_knowledge(
        session, storage, workspace,
        content=b"A study of board governance and independence in Nigerian firms.",
        author="Uadiale, O.", publication_year=2012,
    )
    conversation = StartConversationUseCase(
        SqlAlchemyConversationRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=workspace.agent.user_id)
    provider = FakeTextGenerationProvider(
        reply="Uadiale (2012) found that board independence matters for governance."
    )

    _send_and_process(
        session, storage, workspace, conversation.conversation_id,
        "Discuss board governance and independence.", provider,
    )

    messages = SqlAlchemyMessageRepository(session).list_by_conversation_id(conversation.conversation_id)
    reply = next(m for m in messages if m.origin == "FakeTextGenerationProvider")
    assert "ScholarOS notice" not in reply.content


def test_a_reply_citing_a_fabricated_author_despite_real_evidence_gets_a_warning(session, storage):
    workspace = _make_workspace(session, username="researcher-fake-citation")
    _provision_document_with_knowledge(
        session, storage, workspace,
        content=b"A study of board governance and independence in Nigerian firms.",
        author="Uadiale, O.", publication_year=2012,
    )
    conversation = StartConversationUseCase(
        SqlAlchemyConversationRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    ).execute(user_id=workspace.agent.user_id)
    provider = FakeTextGenerationProvider(reply="Smith and Jones (2019) found no such effect on governance.")

    _send_and_process(
        session, storage, workspace, conversation.conversation_id,
        "Discuss board governance and independence.", provider,
    )

    messages = SqlAlchemyMessageRepository(session).list_by_conversation_id(conversation.conversation_id)
    reply = next(m for m in messages if m.origin == "FakeTextGenerationProvider")
    assert "ScholarOS notice" in reply.content
    assert "Smith and Jones (2019)" in reply.content


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
    a_memory, _ = list_use_case.execute(user_id=workspace_a.agent.user_id)
    b_memory, _ = list_use_case.execute(user_id=workspace_b.agent.user_id)

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
