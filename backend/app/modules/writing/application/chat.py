from app.ai.providers.base import TextGenerationProvider
from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.ports import ContentStore
from app.modules.knowledge.application.retrieval import SearchKnowledgeUseCase
from app.modules.project.domain.repositories import ProjectRepository
from datetime import datetime, timezone

from app.modules.writing.domain.context_assembly import (
    DEFAULT_MAX_CONVERSATION_MESSAGES,
    ContextAssemblyInput,
    ContextEvidence,
    ContextEvidenceSource,
    ContextMemory,
    ContextStyleSignal,
    assemble_context,
)
from app.modules.writing.domain.conversation_context import (
    CONVERSATION_SUMMARY_ORIGIN,
    resolve_bounded_conversation_messages,
)
from app.modules.writing.domain.conversation_summarization import (
    build_conversation_summary_prompt,
    select_messages_to_summarize,
)
from app.modules.writing.domain.entities import Conversation, MemoryProvenanceLink, MemoryRecord, Message
from app.modules.writing.domain.enums import CreatedBy, MemoryProvenanceSourceType, MessageDirection
from app.modules.writing.domain.exceptions import (
    ChatReplyCannotBeRetriedError,
    ChatReplyWorkItemNotFoundError,
    ConversationNotFoundError,
    EmptyGeneratedContentError,
)
from app.modules.writing.domain.memory_extraction import (
    MEMORY_EXTRACTION_TRIGGER_COUNT,
    build_conversation_transcript,
    extract_memories_from_conversation,
)
from app.modules.writing.domain.repositories import (
    ConversationRepository,
    MemoryProvenanceLinkRepository,
    MemoryRecordRepository,
    MessageRepository,
    ProfileCharacteristicRepository,
    WritingProfileRepository,
)
from app.workers.enums import WorkItemKind, WorkItemState
from app.workers.entities import WorkItem
from app.workers.payloads import build_generate_chat_reply_payload_reference, parse_generate_chat_reply_conversation_id
from app.workers.ports import WorkItemEnqueuer, WorkItemOutcomeLookup


class StartConversationUseCase:
    """Opens a new, standalone Agent Workspace conversation (Persistent Brain Decision 3).
    Every call creates a genuinely new Conversation row, since a user may hold several
    concurrent chat threads.
    """

    def __init__(
        self, conversation_repository: ConversationRepository, agent_repository: AgentRepository, unit_of_work: UnitOfWork
    ) -> None:
        self._conversations = conversation_repository
        self._agents = agent_repository
        self._uow = unit_of_work

    def execute(self, *, user_id: int, title: str | None = None) -> Conversation:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        conversation = Conversation(agent_id=agent.agent_id, title=title)
        try:
            persisted = self._conversations.add(conversation)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
        return persisted


class ListConversationsUseCase:
    def __init__(self, conversation_repository: ConversationRepository, agent_repository: AgentRepository) -> None:
        self._conversations = conversation_repository
        self._agents = agent_repository

    def execute(self, *, user_id: int) -> list[Conversation]:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)
        return self._conversations.list_by_agent_id(agent.agent_id)


class ListConversationMessagesUseCase:
    """Enforces the same ownership check as every other Writing read (non-enumeration): a
    Conversation belonging to a different Agent is reported identically to a genuinely missing
    one.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        agent_repository: AgentRepository,
    ) -> None:
        self._conversations = conversation_repository
        self._messages = message_repository
        self._agents = agent_repository

    def execute(self, *, user_id: int, conversation_id: int) -> list[Message]:
        conversation = self._conversations.get_by_id(conversation_id)
        agent = self._agents.get_by_id(conversation.agent_id) if conversation is not None else None
        if (
            conversation is None
            or agent is None
            or agent.user_id != user_id
            or conversation.deleted_at is not None
        ):
            raise ConversationNotFoundError(conversation_id=conversation_id)
        # Rolling summaries are internal context, not assistant replies. Exposing them in the
        # transcript made a long chat appear to receive unsolicited, duplicate assistant
        # messages after every compaction.
        return [
            message
            for message in self._messages.list_by_conversation_id(conversation_id)
            if message.origin != CONVERSATION_SUMMARY_ORIGIN
        ]


class DeleteConversationUseCase:
    """Soft-deletes a standalone Agent Workspace conversation - its Messages are preserved
    (continuity record, never rewritten), but the Conversation itself disappears from
    `GET /writing/conversations` and can no longer be read from or sent to.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        agent_repository: AgentRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._conversations = conversation_repository
        self._agents = agent_repository
        self._uow = unit_of_work

    def execute(self, *, user_id: int, conversation_id: int) -> None:
        conversation = self._conversations.get_by_id(conversation_id)
        agent = self._agents.get_by_id(conversation.agent_id) if conversation is not None else None
        if (
            conversation is None
            or agent is None
            or agent.user_id != user_id
            or conversation.deleted_at is not None
        ):
            raise ConversationNotFoundError(conversation_id=conversation_id)

        try:
            self._conversations.mark_deleted(conversation_id, deleted_at=datetime.now(timezone.utc))
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise


class SendChatMessageUseCase:
    """Resolves a real `ContextAssemblyInput` for one chat message and enqueues its reply:
    topic, description, optional research evidence, writing style, memory, plus this
    Conversation's own bounded recent history.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        agent_repository: AgentRepository,
        project_repository: ProjectRepository,
        writing_profile_repository: WritingProfileRepository,
        profile_characteristic_repository: ProfileCharacteristicRepository,
        memory_record_repository: MemoryRecordRepository,
        search_knowledge_use_case: SearchKnowledgeUseCase,
        work_item_enqueuer: WorkItemEnqueuer,
        content_store: ContentStore,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._conversations = conversation_repository
        self._messages = message_repository
        self._agents = agent_repository
        self._projects = project_repository
        self._writing_profiles = writing_profile_repository
        self._profile_characteristics = profile_characteristic_repository
        self._memory_records = memory_record_repository
        self._search_knowledge = search_knowledge_use_case
        self._work_items = work_item_enqueuer
        self._content_store = content_store
        self._uow = unit_of_work

    def execute(self, *, user_id: int, conversation_id: int, content: str) -> WorkItem:
        conversation = self._conversations.get_by_id(conversation_id)
        agent = self._agents.get_by_id(conversation.agent_id) if conversation is not None else None
        if (
            conversation is None
            or agent is None
            or agent.user_id != user_id
            or conversation.deleted_at is not None
        ):
            raise ConversationNotFoundError(conversation_id=conversation_id)

        project = self._projects.get_by_agent_id(agent.agent_id)
        assert project is not None, f"Agent {agent.agent_id} has no Project (invariant 15 violated)"

        prior_messages = self._messages.list_by_conversation_id(conversation_id)
        conversation_messages = resolve_bounded_conversation_messages(
            prior_messages, max_recent=DEFAULT_MAX_CONVERSATION_MESSAGES
        )

        search_results = self._search_knowledge.execute(user_id=user_id, query=content)
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
            description=project.description,
            instructions=content,
            evidence=evidence,
            style_signals=style_signals,
            memories=memories,
            conversation_messages=conversation_messages,
        )

        self._conversations.lock_for_message_sequence(conversation_id)
        sequence = self._messages.count_by_conversation_id(conversation_id) + 1
        user_message = self._messages.add(
            Message(
                conversation_id=conversation_id,
                sequence=sequence,
                direction=MessageDirection.USER_REQUEST,
                content=content,
            )
        )
        self._uow.commit()

        payload_reference, idempotency_key = build_generate_chat_reply_payload_reference(
            conversation_id, user_message.message_id, context, self._content_store
        )
        try:
            work_item = self._work_items.enqueue(
                kind=WorkItemKind.PIPELINE_STAGE,
                payload_reference=payload_reference,
                idempotency_key=idempotency_key,
            )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
        return work_item


class GetChatReplyStatusUseCase:
    """Lets the frontend distinguish "still generating" from "genuinely failed" for one chat
    reply, instead of the old behavior of silently timing out a fixed poll window with no
    explanation - the same real UX gap `RetryDocumentProcessingUseCase`'s own history already
    found and fixed for document processing (`ListProjectDocumentsUseCase`'s docstring), now
    closed for chat replies too.

    Verifies both that the caller's Conversation is genuinely theirs (existing ownership check)
    *and* that the named work_item_id actually belongs to that Conversation (via the
    conversation_id embedded in its own payload_reference) - without the second check, any
    conversation owner could poll an arbitrary work_item_id and read another conversation's
    generation status/error text.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        agent_repository: AgentRepository,
        work_items: WorkItemOutcomeLookup,
    ) -> None:
        self._conversations = conversation_repository
        self._agents = agent_repository
        self._work_items = work_items

    def execute(self, *, user_id: int, conversation_id: int, work_item_id: int) -> WorkItem:
        conversation = self._conversations.get_by_id(conversation_id)
        agent = self._agents.get_by_id(conversation.agent_id) if conversation is not None else None
        if conversation is None or agent is None or agent.user_id != user_id or conversation.deleted_at is not None:
            raise ConversationNotFoundError(conversation_id=conversation_id)

        work_item = self._work_items.get_by_id(work_item_id)
        if work_item is None or not _belongs_to_conversation(work_item, conversation_id):
            raise ChatReplyWorkItemNotFoundError(work_item_id=work_item_id)
        return work_item


class RetryChatReplyUseCase:
    """Re-enqueues a chat reply generation whose previous attempt terminally `failed` - mirrors
    `RetryDocumentProcessingUseCase` exactly, including reusing the existing Work Item row
    (`WorkItemOutcomeLookup.requeue_failed_by_payload_reference`) rather than enqueuing a new
    one, since `idempotency_key` is already taken by the original attempt.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        agent_repository: AgentRepository,
        work_items: WorkItemOutcomeLookup,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._conversations = conversation_repository
        self._agents = agent_repository
        self._work_items = work_items
        self._uow = unit_of_work

    def execute(self, *, user_id: int, conversation_id: int, work_item_id: int) -> WorkItem:
        conversation = self._conversations.get_by_id(conversation_id)
        agent = self._agents.get_by_id(conversation.agent_id) if conversation is not None else None
        if conversation is None or agent is None or agent.user_id != user_id or conversation.deleted_at is not None:
            raise ConversationNotFoundError(conversation_id=conversation_id)

        work_item = self._work_items.get_by_id(work_item_id)
        if work_item is None or not _belongs_to_conversation(work_item, conversation_id):
            raise ChatReplyWorkItemNotFoundError(work_item_id=work_item_id)
        if work_item.state != WorkItemState.FAILED:
            raise ChatReplyCannotBeRetriedError(work_item_id=work_item_id, state=work_item.state.value)

        try:
            retried = self._work_items.requeue_failed_by_payload_reference(work_item.payload_reference)
            assert retried is not None, "work_item was just confirmed failed above"
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
        return retried


def _belongs_to_conversation(work_item: WorkItem, conversation_id: int) -> bool:
    try:
        return parse_generate_chat_reply_conversation_id(work_item.payload_reference) == conversation_id
    except ValueError:
        return False


class GenerateConversationReplyUseCase:
    """Worker-side counterpart of `SendChatMessageUseCase` - assembles the final prompt,
    calls the AI provider, and persists the reply as a plain Conversation Message.

    **Scalable conversation memory (Persistent Brain v2).** After persisting the reply, checks
    whether this Conversation has grown past `conversation_summarization.
    CONVERSATION_SUMMARY_TRIGGER_COUNT` real messages since its last summary and, if so,
    compacts the older ones into one new rolling summary Message (`conversation_context.
    CONVERSATION_SUMMARY_ORIGIN`), exercising `Conversation.status`/`summarized_at`
    (04_Logical_Data_Model.md §3.9). This never touches or discards any persisted Message - the
    full raw history remains exactly as it was; only what later
    `resolve_bounded_conversation_messages` calls include in a *prompt* changes.

    **Memory extraction, chat-triggered.** The Drafts/Review pipeline that originally triggered
    Memory generation (Persistent Brain Decision 4) was removed entirely - chat is now Memory's
    only automatic source. Every `memory_extraction.MEMORY_EXTRACTION_TRIGGER_COUNT` real
    messages, the most recent stretch of the conversation is distilled into Memory Records the
    same way an approved Draft Version once was, with `MemoryProvenanceSourceType.CONVERSATION`
    provenance instead of `REVIEW_DECISION`.

    Both a summarization and a memory-extraction failure are swallowed, not raised: neither may
    ever turn a successful reply into a failed Work Item and an unbounded retry loop - the
    reply the user is waiting on has already been committed by the time either runs.
    """

    def __init__(
        self,
        message_repository: MessageRepository,
        conversation_repository: ConversationRepository,
        memory_record_repository: MemoryRecordRepository,
        memory_provenance_link_repository: MemoryProvenanceLinkRepository,
        text_provider: TextGenerationProvider,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._messages = message_repository
        self._conversations = conversation_repository
        self._memory_records = memory_record_repository
        self._memory_provenance_links = memory_provenance_link_repository
        self._text_provider = text_provider
        self._uow = unit_of_work

    def execute(self, *, conversation_id: int, context: ContextAssemblyInput) -> Message:
        # A queued reply may outlive a user deleting its conversation. Do not spend an AI call
        # or append a visible message to a conversation that is no longer accessible.
        conversation = self._conversations.get_by_id(conversation_id)
        if conversation is None or conversation.deleted_at is not None:
            raise ConversationNotFoundError(conversation_id=conversation_id)

        assembled = assemble_context(context)
        generated_content = self._text_provider.generate(assembled.prompt)
        if not generated_content or not generated_content.strip():
            raise EmptyGeneratedContentError()

        self._conversations.lock_for_message_sequence(conversation_id)
        sequence = self._messages.count_by_conversation_id(conversation_id) + 1
        message = Message(
            conversation_id=conversation_id,
            sequence=sequence,
            direction=MessageDirection.SYSTEM_RESPONSE,
            content=generated_content.strip(),
            origin=type(self._text_provider).__name__,
        )
        try:
            persisted = self._messages.add(message)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        self._summarize_if_needed(conversation_id)
        self._extract_memory_if_needed(conversation_id, context)
        return persisted

    def _summarize_if_needed(self, conversation_id: int) -> None:
        try:
            all_messages = self._messages.list_by_conversation_id(conversation_id)
            to_summarize = select_messages_to_summarize(all_messages)
            if not to_summarize:
                return

            prior_summary = next(
                (m.content for m in reversed(all_messages) if m.origin == CONVERSATION_SUMMARY_ORIGIN), None
            )
            prompt = build_conversation_summary_prompt(to_summarize, prior_summary=prior_summary)
            summary_text = self._text_provider.generate(prompt)
            if not summary_text or not summary_text.strip():
                return

            self._conversations.lock_for_message_sequence(conversation_id)
            sequence = self._messages.count_by_conversation_id(conversation_id) + 1
            self._messages.add(
                Message(
                    conversation_id=conversation_id,
                    sequence=sequence,
                    direction=MessageDirection.SYSTEM_RESPONSE,
                    content=summary_text.strip(),
                    origin=CONVERSATION_SUMMARY_ORIGIN,
                )
            )
            self._conversations.mark_summarized(conversation_id, summarized_at=datetime.now(timezone.utc))
            self._uow.commit()
        except Exception:
            self._uow.rollback()

    def _extract_memory_if_needed(self, conversation_id: int, context: ContextAssemblyInput) -> None:
        try:
            all_messages = self._messages.list_by_conversation_id(conversation_id)
            # Counts only real messages, excluding any rolling summary _summarize_if_needed may
            # have just injected above - summarization and memory extraction share the same
            # trigger count, and a summary message landing first would otherwise throw off this
            # modulo check on the very turn memory was supposed to fire.
            real_messages = [m for m in all_messages if m.origin != CONVERSATION_SUMMARY_ORIGIN]
            if not real_messages or len(real_messages) % MEMORY_EXTRACTION_TRIGGER_COUNT != 0:
                return

            conversation = self._conversations.get_by_id(conversation_id)
            if conversation is None:
                return

            recent = real_messages[-MEMORY_EXTRACTION_TRIGGER_COUNT:]
            transcript = build_conversation_transcript(recent)
            if not transcript.strip():
                return

            extracted_memories = extract_memories_from_conversation(
                topic=context.topic,
                description=context.description,
                transcript=transcript,
                provider=self._text_provider,
            )
            if not extracted_memories:
                return

            for extracted in extracted_memories:
                record = self._memory_records.add(
                    MemoryRecord(
                        agent_id=conversation.agent_id,
                        record_type=extracted.record_type,
                        content=extracted.content,
                        rationale=extracted.rationale,
                        created_by=CreatedBy.SYSTEM,
                    )
                )
                self._memory_provenance_links.add(
                    MemoryProvenanceLink(
                        record_id=record.record_id,
                        source_type=MemoryProvenanceSourceType.CONVERSATION,
                        conversation_id=conversation_id,
                    )
                )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
