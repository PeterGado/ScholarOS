import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.ai.providers.base import EmbeddingProvider, TextGenerationProvider
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.domain.enums import DocumentProcessingStatus
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.application.use_cases import ExtractDocumentKnowledgeUseCase, ProcessDocumentUseCase
from app.modules.knowledge.domain.text_extraction import PlainTextExtractor
from app.modules.knowledge.infrastructure.repositories import (
    SqlAlchemyChunkEvidenceLinkRepository,
    SqlAlchemyKnowledgeChunkEmbeddingRepository,
    SqlAlchemyKnowledgeChunkRepository,
    SqlAlchemyKnowledgeElementRepository,
)
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.application.use_cases import GenerateDraftVersionUseCase
from app.modules.writing.domain.entities import Message, MessageContextLink
from app.modules.writing.domain.enums import MessageContextTargetType, MessageDirection
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyDraftEvidenceLinkRepository,
    SqlAlchemyDraftRepository,
    SqlAlchemyDraftVersionRepository,
    SqlAlchemyMessageContextLinkRepository,
    SqlAlchemyMessageRepository,
)
from app.storage.filesystem import FilesystemStorage
from app.workers.enums import WorkItemState
from app.workers.payloads import (
    parse_generate_draft_version_payload_reference,
    parse_process_document_payload_reference,
)
from app.workers.repository import WorkItemRepository

logger = logging.getLogger(__name__)


def process_one_work_item(
    session: Session,
    *,
    text_provider: TextGenerationProvider,
    embedding_provider: EmbeddingProvider,
    embedding_model_version: str,
    storage: FilesystemStorage,
) -> bool:
    """Claims and fully processes at most one queued Work Item using `session`.

    Returns True if an item was claimed (regardless of outcome), False if the queue was
    empty. Each phase (claim, execute, record outcome) commits independently, matching
    ADR-006's independently-retryable-stage philosophy - not one giant transaction spanning
    the pipeline run.

    Runs Stage 4 (ProcessDocumentUseCase) and Stage 5 (ExtractDocumentKnowledgeUseCase) as a
    single execution per the Stage 6 plan; `ResearchDocument.processing_status` becomes
    meaningful here for the first time: `processing` while claimed, `processed` on success,
    `pending` while a retry is still pending, `failed` once retries are exhausted.
    """
    uow = SqlAlchemyUnitOfWork(session)
    work_items = WorkItemRepository(session)
    documents = SqlAlchemyDocumentRepository(session)

    item = work_items.claim_next_queued()
    if item is None:
        return False

    try:
        document_id = parse_process_document_payload_reference(
            item.payload_reference)
        work_kind = "document"
    except ValueError as exc:
        try:
            draft_id, context, _request_id, message_id = parse_generate_draft_version_payload_reference(
                item.payload_reference, storage)
            work_kind = "writing"
        except ValueError as writing_exc:
            work_items.mark_failed(item.work_item_id, error=str(writing_exc))
            uow.commit()
            logger.warning(
                "Work item %s has an unrecognized payload reference: %s", item.work_item_id, writing_exc)
            return True

    if work_kind == "writing":
        try:
            generated_version = GenerateDraftVersionUseCase(
                SqlAlchemyDraftRepository(session),
                SqlAlchemyDraftVersionRepository(session),
                SqlAlchemyDraftEvidenceLinkRepository(session),
                text_provider,
                uow,
            ).execute(draft_id=draft_id, context=context)
        except Exception as exc:  # noqa: BLE001 - worker routes all failures through bounded retry
            updated_item = work_items.mark_failed(
                item.work_item_id, error=str(exc))
            uow.commit()
            logger.warning("Work item %s failed (attempt %d): %s",
                           item.work_item_id, updated_item.attempts, exc)
            return True

        if message_id is not None:
            # Closes the instructions-contract gap (Project Writing Stage 8 finding): the
            # instructions Message persisted at request time (RequestDraftGenerationUseCase)
            # is linked here to the Draft Version it actually produced, via the frozen Message
            # Context Link entity (04_Logical_Data_Model.md §4.4) - the same evidence-provenance
            # discipline already applied to Draft Evidence Link, extended to instructions.
            SqlAlchemyMessageContextLinkRepository(session).add(
                MessageContextLink(
                    message_id=message_id,
                    target_type=MessageContextTargetType.DRAFT_VERSION,
                    draft_version_id=generated_version.version_id,
                )
            )
            messages = SqlAlchemyMessageRepository(session)
            source_message = messages.get_by_id(message_id)
            if source_message is not None:
                response = messages.add(
                    Message(
                        conversation_id=source_message.conversation_id,
                        sequence=messages.count_by_conversation_id(source_message.conversation_id) + 1,
                        direction=MessageDirection.SYSTEM_RESPONSE,
                        content=f"Draft Version {generated_version.version_number} generated.",
                        origin=type(text_provider).__name__,
                    )
                )
                SqlAlchemyMessageContextLinkRepository(session).add(
                    MessageContextLink(
                        message_id=response.message_id,
                        target_type=MessageContextTargetType.DRAFT_VERSION,
                        draft_version_id=generated_version.version_id,
                    )
                )
            uow.commit()

        work_items.mark_succeeded(item.work_item_id)
        uow.commit()
        return True

    documents.update_processing_status(
        document_id, DocumentProcessingStatus.PROCESSING)
    uow.commit()

    try:
        projects = SqlAlchemyProjectRepository(session)
        agents = SqlAlchemyAgentRepository(session)
        process_document = ProcessDocumentUseCase(
            documents, storage, PlainTextExtractor())
        extract_knowledge = ExtractDocumentKnowledgeUseCase(
            documents,
            projects,
            agents,
            process_document,
            text_provider,
            embedding_provider,
            embedding_model_version,
            SqlAlchemyKnowledgeElementRepository(session),
            SqlAlchemyKnowledgeChunkRepository(session),
            SqlAlchemyChunkEvidenceLinkRepository(session),
            SqlAlchemyKnowledgeChunkEmbeddingRepository(session),
            uow,
        )
        extract_knowledge.execute(document_id=document_id)
    except Exception as exc:  # noqa: BLE001 - any pipeline failure is a retryable work-item failure
        updated_item = work_items.mark_failed(
            item.work_item_id, error=str(exc))
        next_status = (
            DocumentProcessingStatus.PENDING
            if updated_item.state == WorkItemState.QUEUED
            else DocumentProcessingStatus.FAILED
        )
        documents.update_processing_status(document_id, next_status)
        uow.commit()
        logger.warning("Work item %s failed (attempt %d): %s",
                       item.work_item_id, updated_item.attempts, exc)
        return True

    work_items.mark_succeeded(item.work_item_id)
    documents.update_processing_status(
        document_id, DocumentProcessingStatus.PROCESSED, processed_at=datetime.now(timezone.utc))
    uow.commit()
    return True


class WorkItemExecutorLoop:
    """Thin polling wrapper around `process_one_work_item` (ADR-006 Decision 3: an
    in-process executor for the MVP, no broker). Drains back-to-back queued items before
    falling back to polling on `poll_interval`.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        text_provider: TextGenerationProvider,
        embedding_provider: EmbeddingProvider,
        embedding_model_version: str,
        storage: FilesystemStorage,
        *,
        poll_interval: float = 1.0,
        stale_running_threshold: timedelta = timedelta(minutes=10),
    ) -> None:
        self._session_factory = session_factory
        self._text_provider = text_provider
        self._embedding_provider = embedding_provider
        self._embedding_model_version = embedding_model_version
        self._storage = storage
        self._poll_interval = poll_interval
        self._stale_running_threshold = stale_running_threshold
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._recover_stale_running_items()
        self._task = asyncio.create_task(self._run())

    def _recover_stale_running_items(self) -> None:
        """Runs once, synchronously, before polling begins - recovers Work Items a prior
        process left stuck in `running` (see `WorkItemRepository.requeue_stale_running`'s
        docstring for why this is needed at all). Safe to call unconditionally: on a clean
        start there are no `running` rows left over, so this is a no-op query in the common
        case, mirroring `sync_configured_user`'s own "cheap and idempotent every startup"
        pattern in `main.py`.
        """
        session = self._session_factory()
        try:
            recovered = WorkItemRepository(session).requeue_stale_running(
                stale_after=self._stale_running_threshold
            )
            session.commit()
            if recovered:
                logger.warning(
                    "Recovered %d stale RUNNING work item(s) at executor startup", recovered)
        except Exception:
            session.rollback()
            logger.exception(
                "Failed to recover stale RUNNING work items at executor startup")
        finally:
            session.close()

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            claimed = self._process_one_safely()
            if not claimed:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval)
                except TimeoutError:
                    pass

    def _process_one_safely(self) -> bool:
        session = self._session_factory()
        try:
            return process_one_work_item(
                session,
                text_provider=self._text_provider,
                embedding_provider=self._embedding_provider,
                embedding_model_version=self._embedding_model_version,
                storage=self._storage,
            )
        except Exception:
            logger.exception(
                "Work item executor encountered an unexpected error")
            return False
        finally:
            session.close()
