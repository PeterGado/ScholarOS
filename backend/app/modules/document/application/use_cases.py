from dataclasses import dataclass
from datetime import datetime, timezone

from app.ai.usage_guard import AiUsageGuard
from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.enums import DocumentProcessingStatus, DocumentPurpose
from app.modules.document.domain.exceptions import (
    DocumentCannotBeDeletedError,
    DocumentCannotBeRetriedError,
    EmptyDocumentContentError,
    ResearchDocumentNotFoundError,
    TooManyResearchDocumentsError,
)
from app.modules.document.domain.ports import ContentStore
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.project.domain.exceptions import ProjectNotFoundError
from app.modules.project.domain.repositories import ProjectRepository
from app.workers.enums import WorkItemKind
from app.workers.payloads import build_process_document_idempotency_key, build_process_document_payload_reference
from app.workers.ports import WorkItemEnqueuer, WorkItemOutcomeLookup

_DELETABLE_STATUSES = {DocumentProcessingStatus.PENDING, DocumentProcessingStatus.FAILED}
"""A document may only be deleted before it has contributed anything to the knowledge base:
`pending` (never attempted, or a Work Item never got created for it) and `failed` (permanently
failed extraction, e.g. an unsupported format). `processing` is excluded to avoid racing the
worker; `processed` is excluded by product decision (see DocumentCannotBeDeletedError)."""

MAX_RESEARCH_DOCUMENTS_PER_PROJECT = 20
"""A deliberate cap, not an incidental limitation - each document costs real AI provider calls
to process (classification + embedding), and an unbounded project could exhaust a free-tier
daily quota (or run up a paid one) on its own. See TooManyResearchDocumentsError."""


class UploadResearchDocumentUseCase:
    """Realizes 05_Backend_Architecture.md §10.1: accept and register a Research Document
    within its owning Project (§10.2 - depends on the project service for project
    association). Content is written to the object store first, then the metadata row is
    persisted referencing it - an orphaned file from a failed commit is harmless
    (content-addressed, ADR-004 §5), but a DB row pointing at a missing file is not.

    Enforces ownership (§15.1 API-036/API-037; Constraints invariant 15) transitively:
    Project has no user_id of its own, so ownership is proven via the Project's owning Agent.
    A mismatch is reported as the same ProjectNotFoundError as a genuinely missing project -
    deliberately indistinguishable, the same principle Stage 5's login already applies to
    unknown-username vs wrong-password, so a caller cannot use this endpoint to probe which
    project IDs exist.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        content_store: ContentStore,
        unit_of_work: UnitOfWork,
        work_item_enqueuer: WorkItemEnqueuer,
        ai_usage_guard: AiUsageGuard,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._content_store = content_store
        self._uow = unit_of_work
        self._work_items = work_item_enqueuer
        self._ai_usage_guard = ai_usage_guard

    def execute(
        self,
        *,
        project_id: int,
        user_id: int,
        title: str,
        format: str,
        content: bytes,
        author: str | None = None,
        source: str | None = None,
        extension: str = "",
    ) -> ResearchDocument:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        owning_agent = self._agents.get_by_id(project.agent_id)
        if owning_agent is None or owning_agent.user_id != user_id:
            raise ProjectNotFoundError(project_id=project_id)

        existing_count = len(self._documents.list_by_project_id(project_id, purpose=DocumentPurpose.RESEARCH))
        if existing_count >= MAX_RESEARCH_DOCUMENTS_PER_PROJECT:
            raise TooManyResearchDocumentsError(project_id=project_id, limit=MAX_RESEARCH_DOCUMENTS_PER_PROJECT)

        if not content:
            raise EmptyDocumentContentError()

        # AI usage cap (2026-09-21 security pass): estimated directly from the raw uploaded
        # bytes (classification + embedding cost, later, in the Work Item executor, scales with
        # document size) - a byte-length calc, not app.ai.token_estimate.estimate_tokens(str),
        # since content is bytes, not decoded text (and decoding untrusted upload bytes just to
        # estimate a count isn't worth the cost/risk).
        self._ai_usage_guard.check_and_record(user_id=user_id, estimated_tokens=max(1, len(content) // 4))

        content_reference = self._content_store.save(content, extension=extension)

        try:
            document = ResearchDocument.create(
                project_id=project_id,
                title=title,
                format=format,
                content_reference=content_reference,
                author=author,
                source=source,
                purpose=DocumentPurpose.RESEARCH,
            )
            document = self._documents.add(document)
            self._work_items.enqueue(
                kind=WorkItemKind.PIPELINE_STAGE,
                payload_reference=build_process_document_payload_reference(document.document_id),
                idempotency_key=build_process_document_idempotency_key(document.document_id),
            )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        return document


@dataclass(frozen=True)
class ResearchDocumentWithError:
    """A Research Document bundled with the reason its processing failed, if any - so the
    interface layer never has to make a second per-document Work Item lookup itself (mirrors
    `MemoryRecordWithProvenance`'s own shape). `error_message` is always None for a document
    that isn't currently `failed`.
    """

    document: ResearchDocument
    error_message: str | None


class ListProjectDocumentsUseCase:
    """Lists a Project's Research Documents, most recently used to observe `processing_status`
    transitioning from `pending` -> `processing` -> `processed`/`failed`. Added resolving a
    Frontend milestone Stage 1 finding: `POST /projects/{id}/documents` never had a matching
    read endpoint, even though `DocumentRepository.list_by_project_id` already existed -
    exposing it required no new persistence, only the same ownership-checked read pattern
    `UploadResearchDocumentUseCase` already applies.

    Also surfaces *why* a `failed` document failed (the underlying Work Item's `last_error`) -
    a real gap found via manual use: a document could sit there marked "failed" with the user
    given no way to tell an unsupported-format problem from a transient AI-provider outage.

    Scoped to `DocumentPurpose.RESEARCH` only - a writing-style sample is never submitted to
    the knowledge pipeline (see `UploadWritingStyleDocumentUseCase`), so it would otherwise sit
    here forever at `pending` with no explanation, a real bug found via manual use once
    `DocumentPurpose` existed to actually name the distinction.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        work_items: WorkItemOutcomeLookup,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._work_items = work_items

    def execute(self, *, project_id: int, user_id: int) -> list[ResearchDocumentWithError]:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        owning_agent = self._agents.get_by_id(project.agent_id)
        if owning_agent is None or owning_agent.user_id != user_id:
            raise ProjectNotFoundError(project_id=project_id)

        documents = self._documents.list_by_project_id(project_id, purpose=DocumentPurpose.RESEARCH)
        return [
            ResearchDocumentWithError(document=document, error_message=self._error_message_for(document))
            for document in documents
        ]

    def _error_message_for(self, document: ResearchDocument) -> str | None:
        if document.processing_status != DocumentProcessingStatus.FAILED:
            return None
        work_item = self._work_items.get_by_payload_reference(
            build_process_document_payload_reference(document.document_id)
        )
        return work_item.last_error if work_item is not None else None


class DeleteResearchDocumentUseCase:
    """Deletes a Research Document that was never successfully processed - found necessary
    once real uploads (real .docx files, before .docx extraction was supported) got
    permanently stuck with no way to clear them. Restricted to `pending`/`failed` documents
    only (see `_DELETABLE_STATUSES`): a `processed` document has already contributed real
    Knowledge Elements/Chunks/Embeddings to the Agent's knowledge base, and by product decision
    is no longer shown or manageable through this interface at all - refused here too, not
    only hidden in the UI, so the rule holds even against a direct API call.

    Soft-deletes only (`ResearchDocument.deleted_at`) - the underlying stored content is left
    in place. Deleting it would risk breaking a *different* document that happens to share the
    same content-addressed reference (ADR-004 §5: identical content is stored once); an
    unreferenced file left behind is the same harmless-orphan case this codebase already
    accepts for a failed upload commit.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._uow = unit_of_work

    def execute(self, *, project_id: int, user_id: int, document_id: int) -> None:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        owning_agent = self._agents.get_by_id(project.agent_id)
        if owning_agent is None or owning_agent.user_id != user_id:
            raise ProjectNotFoundError(project_id=project_id)

        document = self._documents.get_by_id(document_id)
        if document is None or document.project_id != project_id or document.deleted_at is not None:
            raise ResearchDocumentNotFoundError(document_id=document_id)

        if document.processing_status not in _DELETABLE_STATUSES:
            raise DocumentCannotBeDeletedError(
                document_id=document_id, processing_status=document.processing_status.value
            )

        try:
            self._documents.mark_deleted(document_id, deleted_at=datetime.now(timezone.utc))
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise


class RetryDocumentProcessingUseCase:
    """Re-enqueues processing for a document whose previous attempt terminally `failed` -
    found necessary the same way `DeleteResearchDocumentUseCase` was: without it, a document
    that failed for a transient reason (e.g. the AI provider's quota was briefly exhausted) had
    no path back to `processed` except deleting it and uploading the exact same file again.

    Resets the existing Work Item back to `queued` (`WorkItemOutcomeLookup.
    requeue_failed_by_payload_reference`) rather than enqueuing a new one - the same
    idempotency_key is already taken by the original attempt. Only `failed` documents are
    retriable; `pending`/`processing` already have a live attempt in flight, and `processed`
    has already contributed real knowledge (mirrors `DeleteResearchDocumentUseCase`'s own
    status-gating).
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        work_items: WorkItemOutcomeLookup,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._work_items = work_items
        self._uow = unit_of_work

    def execute(self, *, project_id: int, user_id: int, document_id: int) -> ResearchDocument:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        owning_agent = self._agents.get_by_id(project.agent_id)
        if owning_agent is None or owning_agent.user_id != user_id:
            raise ProjectNotFoundError(project_id=project_id)

        document = self._documents.get_by_id(document_id)
        if document is None or document.project_id != project_id or document.deleted_at is not None:
            raise ResearchDocumentNotFoundError(document_id=document_id)

        if document.processing_status != DocumentProcessingStatus.FAILED:
            raise DocumentCannotBeRetriedError(
                document_id=document_id, processing_status=document.processing_status.value
            )

        try:
            self._work_items.requeue_failed_by_payload_reference(
                build_process_document_payload_reference(document_id)
            )
            self._documents.update_processing_status(document_id, DocumentProcessingStatus.PENDING)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        document.processing_status = DocumentProcessingStatus.PENDING
        return document
