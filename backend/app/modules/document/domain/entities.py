from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.modules.document.domain.enums import (
    DocumentProcessingStatus,
    DocumentPurpose,
    DoiVerificationStatus,
)
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
    # Added 2026-10-05 alongside author grounding real citations (see context_assembly.py's
    # _format_evidence) - optional, free-standing from `author`, since a user may know one
    # without the other. Deliberately an int, not a free-text string: the whole point is a
    # value the model can be told to reproduce verbatim in an "(Author, Year)" citation, which
    # only works if it's unambiguous.
    publication_year: int | None = None
    # Added 2026-10-06: a DOI the user supplies is checked against Crossref (never trusted at
    # face value) by VerifyDocumentDoiUseCase, run as a non-critical step after knowledge
    # extraction. doi_verification_status stays None until that check actually runs (or if no
    # doi was ever given) - see DoiVerificationStatus's own docstring for why there's no
    # separate PENDING member.
    doi: str | None = None
    doi_verification_status: DoiVerificationStatus | None = None
    processing_status: DocumentProcessingStatus = DocumentProcessingStatus.PENDING
    purpose: DocumentPurpose = DocumentPurpose.RESEARCH
    ingested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
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
        publication_year: int | None = None,
        doi: str | None = None,
        purpose: DocumentPurpose = DocumentPurpose.RESEARCH,
    ) -> "ResearchDocument":
        return cls(
            project_id=project_id,
            title=title,
            format=format,
            content_reference=content_reference,
            author=author,
            source=source,
            publication_year=publication_year,
            doi=doi,
            purpose=purpose,
        )
