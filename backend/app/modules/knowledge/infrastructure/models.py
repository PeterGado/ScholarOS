from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.modules.knowledge.domain.enums import CreatedBy, KnowledgeElementStatus, KnowledgeElementType

__all__ = ["KnowledgeElement", "KnowledgeChunk", "ChunkEvidenceLink"]


class KnowledgeElement(Base):
    """An individual unit of interpreted understanding (04_Logical_Data_Model.md §3.5;
    DR-007 to DR-009).
    """

    __tablename__ = "knowledge_elements"

    element_id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.agent_id"), nullable=False)
    element_type: Mapped[KnowledgeElementType] = mapped_column(
        Enum(KnowledgeElementType, native_enum=False, length=16), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[KnowledgeElementStatus] = mapped_column(
        Enum(KnowledgeElementStatus, native_enum=False, length=16),
        nullable=False,
        default=KnowledgeElementStatus.CURRENT,
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by: Mapped[CreatedBy] = mapped_column(Enum(CreatedBy, native_enum=False, length=16), nullable=False)
    superseded_element_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_elements.element_id"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(nullable=True)


class KnowledgeChunk(Base):
    """A discrete retrievable unit of interpreted knowledge (04_Logical_Data_Model.md §3.7;
    ADR-005). Not a raw text fragment - derives from a Knowledge Element (element_id, not
    null), never directly from a document.
    """

    __tablename__ = "knowledge_chunks"

    chunk_id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.agent_id"), nullable=False)
    element_id: Mapped[int] = mapped_column(ForeignKey("knowledge_elements.element_id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[KnowledgeElementStatus] = mapped_column(
        Enum(KnowledgeElementStatus, native_enum=False, length=16),
        nullable=False,
        default=KnowledgeElementStatus.CURRENT,
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ChunkEvidenceLink(Base):
    """First-class evidence association between a Knowledge Chunk and the Research Document
    it draws from (04_Logical_Data_Model.md §4.1; ADR-005; DR-008). Immutable once created.
    """

    __tablename__ = "chunk_evidence_links"
    __table_args__ = (UniqueConstraint("chunk_id", "document_id", name="uq_chunk_evidence_link_chunk_document"),)

    link_id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("knowledge_chunks.chunk_id"), nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("research_documents.document_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by: Mapped[CreatedBy] = mapped_column(Enum(CreatedBy, native_enum=False, length=16), nullable=False)
