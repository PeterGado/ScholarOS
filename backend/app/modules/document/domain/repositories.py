from abc import ABC, abstractmethod
from datetime import datetime

from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.enums import DocumentProcessingStatus


class DocumentRepository(ABC):
    @abstractmethod
    def get_by_id(self, document_id: int) -> ResearchDocument | None: ...

    @abstractmethod
    def list_by_project_id(self, project_id: int) -> list[ResearchDocument]: ...

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
