import asyncio
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.ai.crossref import CrossrefWork, fetch_crossref_work
from app.ai.exceptions import ProviderContentBlockedError, ProviderRateLimitError
from app.ai.providers.base import EmbeddingProvider, TextGenerationProvider
from app.ai.wikipedia import fetch_wikipedia_background
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import VerifyDocumentDoiUseCase
from app.modules.document.domain.enums import DocumentProcessingStatus
from app.modules.document.domain.exceptions import ResearchDocumentNotFoundError
from app.modules.document.domain.ports import ContentStore
from app.modules.document.infrastructure.repositories import (
    SqlAlchemyDocumentRepository,
)
from app.modules.knowledge.application.use_cases import (
    ExtractDocumentKnowledgeUseCase,
    ProcessDocumentUseCase,
)
from app.modules.knowledge.domain.text_extraction import PlainTextExtractor
from app.modules.knowledge.infrastructure.repositories import (
    SqlAlchemyChunkEvidenceLinkRepository,
    SqlAlchemyKnowledgeChunkEmbeddingRepository,
    SqlAlchemyKnowledgeChunkRepository,
    SqlAlchemyKnowledgeElementRepository,
)
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.application.chat import GenerateConversationReplyUseCase
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMemoryProvenanceLinkRepository,
    SqlAlchemyMemoryRecordRepository,
    SqlAlchemyMessageRepository,
)
from app.workers.enums import WorkItemState
from app.workers.payloads import (
    parse_generate_chat_reply_payload_reference,
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
    storage: ContentStore,
    background_knowledge_provider: Callable[[str], str | None] = fetch_wikipedia_background,
    doi_lookup_provider: Callable[[str], CrossrefWork | None] = fetch_crossref_work,
    enable_multi_pass_generation: bool = True,
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

    `doi_lookup_provider` (2026-10-06) defaults to the real Crossref client, same injection
    pattern as `background_knowledge_provider` - tests must always override it, since the
    default makes a real network call (VerifyDocumentDoiUseCase is a no-op for a document with
    no `doi`, so most tests are unaffected either way, but an e2e test that does set one must
    inject a fake here, exactly like the existing text_provider/embedding_provider fakes).
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
    except ValueError:
        try:
            conversation_id, _user_message_id, chat_context, _chat_request_id = (
                parse_generate_chat_reply_payload_reference(item.payload_reference, storage)
            )
            work_kind = "chat"
        except ValueError as chat_exc:
            work_items.mark_failed(item.work_item_id, error=str(chat_exc))
            uow.commit()
            logger.warning(
                "Work item %s has an unrecognized payload reference: %s", item.work_item_id, chat_exc)
            return True

    if work_kind == "chat":
        try:
            GenerateConversationReplyUseCase(
                SqlAlchemyMessageRepository(session),
                SqlAlchemyConversationRepository(session),
                SqlAlchemyMemoryRecordRepository(session),
                SqlAlchemyMemoryProvenanceLinkRepository(session),
                text_provider,
                uow,
                background_knowledge_provider=background_knowledge_provider,
                enable_multi_pass=enable_multi_pass_generation,
            ).execute(conversation_id=conversation_id, context=chat_context)
        except Exception as exc:  # noqa: BLE001 - worker routes all failures through bounded retry
            updated_item = work_items.mark_failed(
                item.work_item_id,
                error=str(exc),
                # A quota reset needs time, and a safety-blocked message will be blocked again
                # unmodified - immediate automatic attempts only burn through the retry budget
                # and create duplicate provider requests.
                max_attempts=1 if isinstance(exc, (ProviderRateLimitError, ProviderContentBlockedError)) else 3,
            )
            uow.commit()
            logger.warning("Work item %s failed (attempt %d): %s",
                           item.work_item_id, updated_item.attempts, exc)
            return True

        work_items.mark_succeeded(item.work_item_id)
        uow.commit()
        return True

    try:
        documents.update_processing_status(
            document_id, DocumentProcessingStatus.PROCESSING)
        uow.commit()

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

        # DOI verification (2026-10-06) is non-critical enrichment, deliberately outside the
        # try/except above's "any failure retries the whole document" contract - a transient
        # Crossref outage must not turn a successfully-extracted document into a failed one
        # (same reasoning as summarization/memory-extraction failures being swallowed in
        # GenerateConversationReplyUseCase). A no-op when the document has no doi set.
        try:
            VerifyDocumentDoiUseCase(
                documents, uow, doi_lookup_provider=doi_lookup_provider
            ).execute(document_id=document_id)
        except Exception as doi_exc:  # noqa: BLE001 - never let this fail document processing
            logger.warning("DOI verification failed for document %s (non-critical): %s", document_id, doi_exc)
    except Exception as exc:  # noqa: BLE001 - any pipeline failure is a retryable work-item failure
        # A document deleted while its Work Item was still queued (DeleteResearchDocumentUseCase
        # only permits deleting pending/failed documents, exactly the states a queued item can
        # still reference) can never succeed no matter how many times it's retried. Until
        # 2026-09-30, the `update_processing_status` call above sat outside any try/except, so
        # this exact error propagated straight out of this function uncaught - the session was
        # then closed without a commit, silently rolling back the `claim_next_queued` state
        # change, so the *same* oldest queued item was reclaimed and crashed again on every poll,
        # forever, starving every other queued item behind it (including chat replies - this is
        # the root cause of the 2026-09-30 "stuck on Thinking..." outage). Fail it permanently on
        # the first attempt instead of retrying a document lookup that can never succeed.
        document_is_missing = isinstance(exc, ResearchDocumentNotFoundError)
        updated_item = work_items.mark_failed(
            item.work_item_id,
            error=str(exc),
            # A provider daily quota cannot recover during the next polling cycle, and a
            # safety-blocked document will be blocked again unmodified. Preserve the failed
            # item for the existing explicit Retry action instead.
            max_attempts=1
            if (document_is_missing or isinstance(exc, (ProviderRateLimitError, ProviderContentBlockedError)))
            else 3,
        )
        if not document_is_missing:
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
        document_id, DocumentProcessingStatus.PROCESSED, processed_at=datetime.now(UTC))
    uow.commit()
    return True


class WorkItemExecutorLoop:
    """Polling wrapper around `process_one_work_item` (ADR-006 Decision 3: an in-process
    executor for the MVP, no broker), running `worker_count` concurrent OS threads rather than
    asyncio tasks (2026-09-30, found while planning concurrent Work Item processing): every
    frame below `_process_one_safely` - the SQLAlchemy `Session` (sync, not `AsyncSession`) and
    the `google-genai` SDK client (sync, not its `.aio` client) - is fully blocking, synchronous
    code with no `await` anywhere inside it. Calling that directly from an `async def` loop, as
    this class used to, holds the single event loop thread hostage for the full duration of
    every AI call or document-processing run - freezing every concurrent HTTP request in the
    whole process, not just other queued items, and making N concurrent `asyncio.Task`s worth
    zero extra throughput regardless of N, since only one can ever be inside the blocking call
    at a time. Real `threading.Thread`s let the OS actually run them concurrently during I/O
    waits (DB round trips, outbound AI HTTP calls both release the GIL), which is what this
    workload actually needs - matching the fully-synchronous shape of everything it calls
    instead of dressing it up in an async wrapper that must never contain a blocking call.
    Drains back-to-back queued items before falling back to polling on `poll_interval`.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        text_provider: TextGenerationProvider,
        embedding_provider: EmbeddingProvider,
        embedding_model_version: str,
        storage: ContentStore,
        *,
        poll_interval: float = 1.0,
        stale_running_threshold: timedelta = timedelta(minutes=10),
        worker_count: int = 1,
        background_knowledge_provider: Callable[[str], str | None] = fetch_wikipedia_background,
        enable_multi_pass_generation: bool = True,
    ) -> None:
        self._session_factory = session_factory
        self._text_provider = text_provider
        self._embedding_provider = embedding_provider
        self._embedding_model_version = embedding_model_version
        self._storage = storage
        self._poll_interval = poll_interval
        self._stale_running_threshold = stale_running_threshold
        self._worker_count = worker_count
        self._background_knowledge_provider = background_knowledge_provider
        self._enable_multi_pass_generation = enable_multi_pass_generation
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        self._recover_stale_running_items()
        self._threads = [
            threading.Thread(target=self._run, name=f"work-item-worker-{i}", daemon=True)
            for i in range(self._worker_count)
        ]
        for thread in self._threads:
            thread.start()

    def _recover_stale_running_items(self) -> None:
        """Runs once, synchronously, before polling begins - recovers Work Items a prior
        process left stuck in `running` (see `WorkItemRepository.requeue_stale_running`'s
        docstring for why this is needed at all). Safe to call unconditionally: on a clean
        start there are no `running` rows left over, so this is a no-op query in the common
        case, mirroring `sync_configured_user`'s own "cheap and idempotent every startup"
        pattern in `main.py`. Runs once regardless of `worker_count` - it's startup recovery,
        not a per-worker concern.
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
        # The only legitimate blocking wait in this class - a one-time join at shutdown, never
        # in the hot polling path. Offloaded via to_thread so it doesn't itself block the event
        # loop while threads finish whatever item they're mid-processing.
        await asyncio.to_thread(self._join_all)

    def _join_all(self) -> None:
        for thread in self._threads:
            thread.join()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            claimed = self._process_one_safely()
            if not claimed:
                self._stop_event.wait(timeout=self._poll_interval)

    def _process_one_safely(self) -> bool:
        session = self._session_factory()
        try:
            return process_one_work_item(
                session,
                text_provider=self._text_provider,
                embedding_provider=self._embedding_provider,
                embedding_model_version=self._embedding_model_version,
                storage=self._storage,
                background_knowledge_provider=self._background_knowledge_provider,
                enable_multi_pass_generation=self._enable_multi_pass_generation,
            )
        except Exception:
            logger.exception(
                "Work item executor encountered an unexpected error")
            return False
        finally:
            session.close()
