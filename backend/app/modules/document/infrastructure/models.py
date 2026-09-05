from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.modules.document.domain.enums import DocumentProcessingStatus

__all__ = ["ResearchDocument", "DocumentProcessingStatus"]


class ResearchDocument(Base):
    """Document Service persistence (05_Backend_Architecture.md §10; 04_Logical_Data_Model.md §3.4).

    `format` is stored as a plain string, not a fixed Python enum: the Logical Data Model
    marks it "Enumerated - supplied format family" but no approved document enumerates its
    member values. Encoding a guessed set here would invent an undocumented business rule;
    left open for the stage that actually defines accepted document formats.
    """

    __tablename__ = "research_documents"

    document_id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    format: Mapped[str] = mapped_column(String(64), nullable=False)
    content_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        Enum(DocumentProcessingStatus, native_enum=False, length=16),
        nullable=False,
        default=DocumentProcessingStatus.PENDING,
    )
    ingested_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
