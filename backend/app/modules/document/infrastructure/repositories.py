from sqlalchemy.orm import Session

from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.document.infrastructure.models import ResearchDocument as ResearchDocumentModel


class SqlAlchemyDocumentRepository(DocumentRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, document_id: int) -> ResearchDocument | None:
        row = self._session.get(ResearchDocumentModel, document_id)
        return self._to_domain(row) if row is not None else None

    def list_by_project_id(self, project_id: int) -> list[ResearchDocument]:
        rows = self._session.query(ResearchDocumentModel).filter_by(project_id=project_id).all()
        return [self._to_domain(row) for row in rows]

    def add(self, document: ResearchDocument) -> ResearchDocument:
        row = ResearchDocumentModel(
            project_id=document.project_id,
            title=document.title,
            author=document.author,
            source=document.source,
            format=document.format,
            content_reference=document.content_reference,
            processing_status=document.processing_status,
        )
        self._session.add(row)
        self._session.flush()
        document.document_id = row.document_id
        document.ingested_at = row.ingested_at
        return document

    @staticmethod
    def _to_domain(row: ResearchDocumentModel) -> ResearchDocument:
        return ResearchDocument(
            document_id=row.document_id,
            project_id=row.project_id,
            title=row.title,
            author=row.author,
            source=row.source,
            format=row.format,
            content_reference=row.content_reference,
            processing_status=row.processing_status,
            ingested_at=row.ingested_at,
            processed_at=row.processed_at,
            deleted_at=row.deleted_at,
        )
