from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.modules.document.domain.enums import DocumentProcessingStatus
from app.modules.document.domain.exceptions import (
    EmptyDocumentContentError,
    InvalidDocumentFormatError,
    InvalidDocumentTitleError,
)


@dataclass
class ResearchDocument:
    """User-supplied source material retained as evidence (04_Logical_Data_Model.md §3.4).

    `ingested_at` and `content_reference` are immutable after creation
    (05_Constraints_and_Integrity.md §5).

    `format` is intentionally unconstrained beyond "non-empty": no approved document
    (SRS/Architecture/ADR) enumerates accepted format values (flagged in Stage 3's report).
    """

    project_id: int
    title: str
    format: str
    content_reference: str
    document_id: int | None = None
    author: str | None = None
    source: str | None = None
    processing_status: DocumentProcessingStatus = DocumentProcessingStatus.PENDING
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise InvalidDocumentTitleError()
        if not self.format or not self.format.strip():
            raise InvalidDocumentFormatError()
        if not self.content_reference or not self.content_reference.strip():
            raise EmptyDocumentContentError()

    @classmethod
    def create(
        cls,
        *,
        project_id: int,
        title: str,
        format: str,
        content_reference: str,
        author: str | None = None,
        source: str | None = None,
    ) -> "ResearchDocument":
        return cls(
            project_id=project_id,
            title=title,
            format=format,
            content_reference=content_reference,
            author=author,
            source=source,
        )
