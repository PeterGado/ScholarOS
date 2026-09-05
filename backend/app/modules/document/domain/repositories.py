from abc import ABC, abstractmethod

from app.modules.document.domain.entities import ResearchDocument


class DocumentRepository(ABC):
    @abstractmethod
    def get_by_id(self, document_id: int) -> ResearchDocument | None: ...

    @abstractmethod
    def list_by_project_id(self, project_id: int) -> list[ResearchDocument]: ...

    @abstractmethod
    def add(self, document: ResearchDocument) -> ResearchDocument: ...
