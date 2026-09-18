from datetime import datetime

from pydantic import BaseModel

from app.modules.document.application.use_cases import ResearchDocumentWithError
from app.modules.document.domain.entities import ResearchDocument


class ResearchDocumentResponse(BaseModel):
    """Response for POST /projects/{project_id}/documents and GET .../documents.

    `content_reference` (the object-store key) is deliberately excluded: it is a storage
    implementation detail, not part of the public contract (ADR-008). `error_message` is
    always null except for a `failed` document, where it carries the underlying Work Item's
    `last_error` - so a user can tell an unsupported-format problem from a transient AI-provider
    outage instead of just seeing "failed" with no explanation.
    """

    document_id: int
    project_id: int
    title: str
    author: str | None
    source: str | None
    format: str
    processing_status: str
    ingested_at: datetime
    error_message: str | None = None

    @classmethod
    def from_domain(cls, document: ResearchDocument, *, error_message: str | None = None) -> "ResearchDocumentResponse":
        return cls(
            document_id=document.document_id,
            project_id=document.project_id,
            title=document.title,
            author=document.author,
            source=document.source,
            format=document.format,
            processing_status=document.processing_status.value,
            ingested_at=document.ingested_at,
            error_message=error_message,
        )


class ResearchDocumentListResponse(BaseModel):
    documents: list[ResearchDocumentResponse]

    @classmethod
    def from_domain(cls, documents: list[ResearchDocumentWithError]) -> "ResearchDocumentListResponse":
        return cls(
            documents=[
                ResearchDocumentResponse.from_domain(item.document, error_message=item.error_message)
                for item in documents
            ]
        )
