from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.knowledge.application.retrieval import SearchKnowledgeUseCase
from app.modules.project.domain.repositories import ProjectRepository
from app.modules.writing.application.use_cases import EnqueueDraftGenerationUseCase
from app.modules.writing.domain.context_assembly import (
    ContextAssemblyInput,
    ContextEvidence,
    ContextEvidenceSource,
    ContextMemory,
    ContextStyleSignal,
)
from app.modules.writing.domain.entities import Conversation, Message
from app.modules.writing.domain.enums import MessageDirection
from app.modules.writing.domain.exceptions import DraftNotFoundError, InsufficientDraftEvidenceError
from app.modules.writing.domain.repositories import (
    ConversationRepository,
    DraftRepository,
    MemoryRecordRepository,
    MessageRepository,
    ProfileCharacteristicRepository,
    WritingProfileRepository,
)
from app.workers.entities import WorkItem


def _draft_conversation_title(draft_id: int) -> str:
    """The association key used to find-or-create "the Conversation for Draft N" via
    Conversation's genuinely free-form `title` field, rather than adding a `draft_id` column to
    the frozen Conversation shape (see `Conversation`'s own docstring, domain/entities.py).
    """
    return f"draft:{draft_id}:instructions"


class RequestDraftGenerationUseCase:
    """Resolves a real `ContextAssemblyInput` for a Draft from an authenticated user's plain
    generation instructions, then delegates to the existing, unmodified Stage 6
    `EnqueueDraftGenerationUseCase` to persist and enqueue it.

    **Why this exists (Stage 7 reconnaissance finding):** Stage 5/6 both deliberately take an
    already-resolved `ContextAssemblyInput` as a parameter - their own documented boundary
    ("the caller supplies already-resolved... Stage 5 does not perform repository retrieval").
    Nothing before Stage 7 ever built the piece that actually resolves one from a bare
    "generate my draft" HTTP request. Naively exposing `EnqueueDraftGenerationUseCase` to
    a route that accepts `ContextAssemblyInput.evidence` directly from the client would be
    unsafe: a client could claim arbitrary chunk_id/content pairs as "evidence" and have them
    persisted as real `Draft Evidence Link` rows, defeating the entire evidence-provenance
    design research retrieval was built for. This use case closes that gap by composing two
    already-built capabilities - Knowledge retrieval (Slice 2 Stage 8's `SearchKnowledgeUseCase`)
    and Stage 6's enqueue - rather than introducing a new architectural mechanism or modifying
    either of them.

    Evidence is the only hard requirement (mirrors `GenerateDraftVersionUseCase`'s own
    `InsufficientDraftEvidenceError`, raised here instead so the HTTP caller gets an immediate,
    synchronous rejection rather than an opaque async Work Item failure). Style signals and
    memories are optional and silently empty when the Agent has none yet - Context Assembly
    already renders that gracefully ("No writing-style signals were available.", etc.).
    """

    def __init__(
        self,
        draft_repository: DraftRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        writing_profile_repository: WritingProfileRepository,
        profile_characteristic_repository: ProfileCharacteristicRepository,
        memory_record_repository: MemoryRecordRepository,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        search_knowledge_use_case: SearchKnowledgeUseCase,
        enqueue_generation_use_case: EnqueueDraftGenerationUseCase,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._drafts = draft_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._writing_profiles = writing_profile_repository
        self._profile_characteristics = profile_characteristic_repository
        self._memory_records = memory_record_repository
        self._conversations = conversation_repository
        self._messages = message_repository
        self._search_knowledge = search_knowledge_use_case
        self._enqueue_generation = enqueue_generation_use_case
        self._uow = unit_of_work

    def execute(self, *, user_id: int, draft_id: int, instructions: str) -> WorkItem:
        draft = self._drafts.get_by_id(draft_id)
        agent = self._agents.get_by_id(draft.agent_id) if draft is not None else None
        if draft is None or agent is None or agent.user_id != user_id:
            raise DraftNotFoundError(draft_id=draft_id)

        # Defensive, not expected to fail: an Agent always owns exactly one permanent Project
        # (05_Constraints_and_Integrity.md invariant 15).
        project = self._projects.get_by_agent_id(agent.agent_id)
        assert project is not None, f"Agent {agent.agent_id} has no Project (invariant 15 violated)"

        search_results = self._search_knowledge.execute(user_id=user_id, query=instructions)
        if not search_results:
            raise InsufficientDraftEvidenceError(draft_id=draft_id)
        evidence = tuple(
            ContextEvidence(
                chunk_id=result.chunk_id,
                content=result.content,
                summary=result.summary,
                score=result.score,
                sources=tuple(
                    ContextEvidenceSource(document_id=source.document_id, document_title=source.document_title)
                    for source in result.evidence
                ),
            )
            for result in search_results
        )

        profile = self._writing_profiles.get_active_by_agent_id(agent.agent_id)
        style_signals = (
            tuple(
                ContextStyleSignal(
                    characteristic_type=characteristic.characteristic_type,
                    signal=characteristic.signal,
                    confidence=characteristic.confidence,
                )
                for characteristic in self._profile_characteristics.list_by_profile_id(profile.profile_id)
            )
            if profile is not None
            else ()
        )

        memories = tuple(
            ContextMemory(record_type=record.record_type, content=record.content, rationale=record.rationale)
            for record in self._memory_records.list_current_by_agent_id(agent.agent_id)
        )

        context = ContextAssemblyInput(
            topic=project.topic,
            instructions=instructions,
            evidence=evidence,
            style_signals=style_signals,
            memories=memories,
        )

        message = self._persist_instructions_message(agent_id=agent.agent_id, draft_id=draft_id, instructions=instructions)
        return self._enqueue_generation.execute(
            user_id=user_id, draft_id=draft_id, context=context, message_id=message.message_id
        )

    def _persist_instructions_message(self, *, agent_id: int, draft_id: int, instructions: str) -> Message:
        """Realizes Stage 1 plan §19 item 3: persists these generation instructions as a
        Message in a Draft-scoped Conversation (found-or-created via `title`, see
        `_draft_conversation_title`) instead of only ever passing them through as an ephemeral
        request field - closing the Stage 8 validation finding that this decision had been
        ratified but never implemented.
        """
        title = _draft_conversation_title(draft_id)
        conversation = self._conversations.get_by_agent_id_and_title(agent_id, title)
        if conversation is None:
            conversation = self._conversations.add(Conversation(agent_id=agent_id, title=title))

        sequence = self._messages.count_by_conversation_id(conversation.conversation_id) + 1
        message = self._messages.add(
            Message(
                conversation_id=conversation.conversation_id,
                sequence=sequence,
                direction=MessageDirection.USER_REQUEST,
                content=instructions,
            )
        )
        self._uow.commit()
        return message
