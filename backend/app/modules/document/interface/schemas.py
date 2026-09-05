from datetime import datetime

from pydantic import BaseModel

from app.modules.document.domain.entities import ResearchDocument


class ResearchDocumentResponse(BaseModel):
    """Response for POST /projects/{project_id}/documents.

    `content_reference` (the object-store key) is deliberately excluded: it is a storage
    implementation detail, not part of the public contract (ADR-008).
    """

    document_id: int
    project_id: int
    title: str
    author: str | None
    source: str | None
    format: str
    processing_status: str
    ingested_at: datetime

    @classmethod
    def from_domain(cls, document: ResearchDocument) -> "ResearchDocumentResponse":
        return cls(
            document_id=document.document_id,
            project_id=document.project_id,
            title=document.title,
            author=document.author,
            source=document.source,
            format=document.format,
            processing_status=document.processing_status.value,
            ingested_at=document.ingested_at,
        )
