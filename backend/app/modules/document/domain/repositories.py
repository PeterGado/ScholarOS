from abc import ABC, abstractmethod
from datetime import datetime

from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.enums import DocumentProcessingStatus, DocumentPurpose, DoiVerificationStatus


class DocumentRepository(ABC):
    @abstractmethod
    def get_by_id(self, document_id: int) -> ResearchDocument | None: ...

    @abstractmethod
    def get_by_ids(self, document_ids: list[int]) -> list[ResearchDocument]:
        """Batch form of `get_by_id` (2026-09-23, real-traffic N+1 fix) - see
        `SearchKnowledgeUseCase`, which previously fetched one Research Document per evidence
        link instead of one query for every document a search result set references. Order is
        not guaranteed to match `document_ids`.
        """
        ...

    @abstractmethod
    def list_by_project_id(
        self,
        project_id: int,
        *,
        purpose: DocumentPurpose | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ResearchDocument]:
        """`purpose=None` lists every non-deleted document regardless of purpose; passing
        `DocumentPurpose.RESEARCH` or `.WRITING_STYLE_SAMPLE` scopes to just that kind - see
        `DocumentPurpose`'s own docstring for why documents need a purpose at all.

        `limit=None` (the default) is unbounded - what the existing upload-count-check callers
        (`MAX_RESEARCH_DOCUMENTS_PER_PROJECT`/`MAX_WRITING_STYLE_SAMPLES`) still get, since they
        need the true full count, not a page. `limit`/`offset` (2026-09-23, pagination for
        `GET /projects/{id}/documents` and `GET /writing/style-profile/documents`) return up to
        `limit + 1` rows so the caller can detect "more exist" without a second COUNT query.
        """
        ...

    @abstractmethod
    def add(self, document: ResearchDocument) -> ResearchDocument: ...

    @abstractmethod
    def update_processing_status(
        self, document_id: int, status: DocumentProcessingStatus, *, processed_at: datetime | None = None
    ) -> None:
        """Added Stage 6 (Async Dispatch): the only way `processing_status`/`processed_at`
        are ever changed after creation - previously no write path existed at all.
        """
        ...

    @abstractmethod
    def update_doi_verification(
        self,
        document_id: int,
        *,
        status: DoiVerificationStatus,
        author: str | None,
        publication_year: int | None,
    ) -> None:
        """Persists the outcome of VerifyDocumentDoiUseCase's Crossref check (2026-10-06).
        `author`/`publication_year` are written unconditionally (not merged) - the use case
        itself decides whether to keep the user's existing values or fill them from the
        verified Crossref record, so this method just stores whatever it's given.
        """
        ...

    @abstractmethod
    def mark_deleted(self, document_id: int, *, deleted_at: datetime) -> None:
        """Soft-deletes a Research Document (exercises the frozen `deleted_at` field for the
        first time - see `DeleteResearchDocumentUseCase` for why deletion is restricted to
        documents that were never successfully processed). `list_by_project_id` excludes
        soft-deleted rows; the row itself, and its stored content, are never removed.
        """
        ...
