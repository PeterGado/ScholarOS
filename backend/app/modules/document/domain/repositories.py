from abc import ABC, abstractmethod
from datetime import datetime

from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.enums import DocumentProcessingStatus, DocumentPurpose


class DocumentRepository(ABC):
    @abstractmethod
    def get_by_id(self, document_id: int) -> ResearchDocument | None: ...

    @abstractmethod
    def list_by_project_id(
        self, project_id: int, *, purpose: DocumentPurpose | None = None
    ) -> list[ResearchDocument]:
        """`purpose=None` lists every non-deleted document regardless of purpose; passing
        `DocumentPurpose.RESEARCH` or `.WRITING_STYLE_SAMPLE` scopes to just that kind - see
        `DocumentPurpose`'s own docstring for why documents need a purpose at all.
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
    def mark_deleted(self, document_id: int, *, deleted_at: datetime) -> None:
        """Soft-deletes a Research Document (exercises the frozen `deleted_at` field for the
        first time - see `DeleteResearchDocumentUseCase` for why deletion is restricted to
        documents that were never successfully processed). `list_by_project_id` excludes
        soft-deleted rows; the row itself, and its stored content, are never removed.
        """
        ...
