from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Enum, Float, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.modules.writing.domain.enums import (
    CreatedBy,
    DraftEvidenceTargetType,
    DraftStatus,
    MemoryProvenanceSourceType,
    MemoryRecordStatus,
    MemoryRecordType,
    ProfileCharacteristicType,
    ReviewOutcome,
    ReviewStatus,
    WritingProfileStatus,
)

__all__ = [
    "Draft",
    "DraftVersion",
    "Review",
    "ReviewDecision",
    "DraftEvidenceLink",
    "WritingProfile",
    "ProfileCharacteristic",
    "ProfileCharacteristicSource",
    "MemoryRecord",
    "MemoryProvenanceLink",
]


def _enum_column(enum_cls: type, length: int):
    """SQLAlchemy's `Enum` type, given a Python `enum.Enum` class, stores each member's
    `.name` (e.g. "OPEN") by default, not its `.value` (e.g. "open") - invisible through the
    ORM (round-trips correctly as Python enum objects either way), but this module's CHECK
    constraints and partial unique indexes are raw SQL comparing against the frozen data
    model's documented lowercase enumerated values (04_Logical_Data_Model.md §2.1 "Enumerated"
    families). `values_callable` makes the stored column value the actual documented value,
    not the Python identifier - found and fixed during Stage 2 (see the Stage 2 completion
    report's Deviations section: this default is also present, unfixed, in every pre-existing
    module - agent/document/knowledge - and is reported there rather than silently changed).
    """

    return Enum(enum_cls, native_enum=False, length=length, values_callable=lambda x: [member.value for member in x])


class Draft(Base):
    """Writing Service persistence (04_Logical_Data_Model.md §3.15; DR-016 to DR-019).
    Realizes an already-frozen entity that had no prior implementation (Project_Writing_
    Implementation_Plan.md §4/§13).
    """

    __tablename__ = "drafts"

    draft_id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.agent_id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[DraftStatus] = mapped_column(
        _enum_column(DraftStatus, 16), nullable=False, default=DraftStatus.DRAFTING
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class DraftVersion(Base):
    """An immutable state of a Draft (04_Logical_Data_Model.md §3.16; DR-017; MVP-021;
    AIR-035). No update path is exposed anywhere in this module - immutability is enforced by
    the absence of a mutating repository method, matching the existing convention for
    Knowledge Element / Chunk Evidence Link (app/modules/knowledge/infrastructure/models.py).
    """

    __tablename__ = "draft_versions"
    __table_args__ = (UniqueConstraint("draft_id", "version_number", name="uq_draft_version_draft_number"),)

    version_id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.draft_id"), nullable=False)
    version_number: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by: Mapped[CreatedBy] = mapped_column(_enum_column(CreatedBy, 16), nullable=False)


class Review(Base):
    """An evaluation round applied to a Draft Version (04_Logical_Data_Model.md §3.17;
    DR-019; WR-022 to WR-025).

    The partial unique index enforces invariant 7 ("at most one open Review per Draft
    Version") at the database layer, not only in application logic
    (05_Constraints_and_Integrity.md invariant 7).
    """

    __tablename__ = "reviews"
    __table_args__ = (
        Index(
            "uq_review_one_open_per_draft_version",
            "draft_version_id",
            unique=True,
            sqlite_where=text("status = 'open'"),
        ),
    )

    review_id: Mapped[int] = mapped_column(primary_key=True)
    draft_version_id: Mapped[int] = mapped_column(ForeignKey("draft_versions.version_id"), nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(
        _enum_column(ReviewStatus, 16), nullable=False, default=ReviewStatus.OPEN
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ReviewDecision(Base):
    """The recorded outcome of a Review, preserved for audit (04_Logical_Data_Model.md
    §3.18; DR-019; AIR-054; MVP-018 to MVP-020). `review_id` is unique - one decision per
    review (invariant 7).
    """

    __tablename__ = "review_decisions"

    decision_id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.review_id"), nullable=False, unique=True)
    outcome: Mapped[ReviewOutcome] = mapped_column(_enum_column(ReviewOutcome, 32), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)


class DraftEvidenceLink(Base):
    """Evidence annotation connecting a Draft Version to the Knowledge Chunk or Research
    Document that supports it (04_Logical_Data_Model.md §4.2; DR-018; AIR-027). Immutable and
    non-cascading (05_Constraints_and_Integrity.md line 199) - no update method is exposed.

    References the existing Knowledge/Document entities by table name only (no cross-module
    Python import), the same pattern already used by Chunk Evidence Link
    (app/modules/knowledge/infrastructure/models.py) - Writing does not duplicate Knowledge
    Element/Chunk/Chunk Evidence Link (Project_Writing_Implementation_Plan.md §17).
    """

    __tablename__ = "draft_evidence_links"
    __table_args__ = (
        # A plain UniqueConstraint on (draft_version_id, target_type, chunk_id, document_id)
        # would NOT catch duplicates: SQL treats NULL <> NULL, so two rows sharing the same
        # chunk_id but both with document_id=NULL are never considered equal by a composite
        # UNIQUE constraint. Partial unique indexes, one per exclusive-arc branch, are the
        # correct way to enforce "no duplicate evidence statements"
        # (05_Constraints_and_Integrity.md line 315) here.
        Index(
            "uq_draft_evidence_link_chunk_target",
            "draft_version_id",
            "chunk_id",
            unique=True,
            sqlite_where=text("chunk_id IS NOT NULL"),
        ),
        Index(
            "uq_draft_evidence_link_document_target",
            "draft_version_id",
            "document_id",
            unique=True,
            sqlite_where=text("document_id IS NOT NULL"),
        ),
        CheckConstraint(
            "(target_type = 'knowledge_chunk' AND chunk_id IS NOT NULL AND document_id IS NULL) OR "
            "(target_type = 'research_document' AND document_id IS NOT NULL AND chunk_id IS NULL)",
            name="ck_draft_evidence_link_exclusive_target",
        ),
    )

    link_id: Mapped[int] = mapped_column(primary_key=True)
    draft_version_id: Mapped[int] = mapped_column(ForeignKey("draft_versions.version_id"), nullable=False)
    target_type: Mapped[DraftEvidenceTargetType] = mapped_column(
        _enum_column(DraftEvidenceTargetType, 32), nullable=False
    )
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_chunks.chunk_id"), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("research_documents.document_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by: Mapped[CreatedBy] = mapped_column(_enum_column(CreatedBy, 16), nullable=False)


class WritingProfile(Base):
    """The author's preserved writing characteristics (04_Logical_Data_Model.md §3.11;
    DR-010 to DR-012). The partial unique index enforces invariant 8 ("at most one active
    Writing Profile per Agent") at the database layer.
    """

    __tablename__ = "writing_profiles"
    __table_args__ = (
        Index(
            "uq_writing_profile_one_active_per_agent",
            "agent_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
    )

    profile_id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.agent_id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[WritingProfileStatus] = mapped_column(
        _enum_column(WritingProfileStatus, 16), nullable=False, default=WritingProfileStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ProfileCharacteristic(Base):
    """A single preserved stylistic attribute (04_Logical_Data_Model.md §3.12; DR-010, DR-012)."""

    __tablename__ = "profile_characteristics"

    characteristic_id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("writing_profiles.profile_id"), nullable=False)
    characteristic_type: Mapped[ProfileCharacteristicType] = mapped_column(
        _enum_column(ProfileCharacteristicType, 16), nullable=False
    )
    signal: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)


class ProfileCharacteristicSource(Base):
    """Provenance of a Profile Characteristic to the authored sample that informed it
    (04_Logical_Data_Model.md §4.5; DR-012).
    """

    __tablename__ = "profile_characteristic_sources"
    __table_args__ = (
        UniqueConstraint("characteristic_id", "document_id", name="uq_profile_characteristic_source"),
    )

    link_id: Mapped[int] = mapped_column(primary_key=True)
    characteristic_id: Mapped[int] = mapped_column(
        ForeignKey("profile_characteristics.characteristic_id"), nullable=False
    )
    document_id: Mapped[int] = mapped_column(ForeignKey("research_documents.document_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)


class MemoryRecord(Base):
    """Persistent project context and decision history with supersession
    (04_Logical_Data_Model.md §3.8; DR-013 to DR-015).
    """

    __tablename__ = "memory_records"

    record_id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.agent_id"), nullable=False)
    record_type: Mapped[MemoryRecordType] = mapped_column(
        _enum_column(MemoryRecordType, 16), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MemoryRecordStatus] = mapped_column(
        _enum_column(MemoryRecordStatus, 16), nullable=False, default=MemoryRecordStatus.CURRENT
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by: Mapped[CreatedBy] = mapped_column(_enum_column(CreatedBy, 16), nullable=False)
    superseded_record_id: Mapped[int | None] = mapped_column(ForeignKey("memory_records.record_id"), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(nullable=True)


class MemoryProvenanceLink(Base):
    """Traces a Memory Record to the artifact or activity that produced it
    (04_Logical_Data_Model.md §4.3; DR-015).

    `conversation_id` deliberately carries no ForeignKey: Conversation is a frozen entity
    (04_Logical_Data_Model.md §3.9) deferred out of Stage 2 (Stage 2 prompt §40) - see the
    domain entity's docstring (domain/entities.py) for the full reasoning. The CHECK
    constraint below encodes the same "user_input -> zero references, else exactly one"
    interpretation implemented in the domain layer (domain/entities.py).
    """

    __tablename__ = "memory_provenance_links"
    __table_args__ = (
        CheckConstraint(
            "(source_type = 'user_input' AND review_decision_id IS NULL AND conversation_id IS NULL "
            "AND element_id IS NULL AND document_id IS NULL AND draft_version_id IS NULL) OR "
            "(source_type = 'review_decision' AND review_decision_id IS NOT NULL AND conversation_id IS NULL "
            "AND element_id IS NULL AND document_id IS NULL AND draft_version_id IS NULL) OR "
            "(source_type = 'conversation' AND conversation_id IS NOT NULL AND review_decision_id IS NULL "
            "AND element_id IS NULL AND document_id IS NULL AND draft_version_id IS NULL) OR "
            "(source_type = 'knowledge_element' AND element_id IS NOT NULL AND review_decision_id IS NULL "
            "AND conversation_id IS NULL AND document_id IS NULL AND draft_version_id IS NULL) OR "
            "(source_type = 'document' AND document_id IS NOT NULL AND review_decision_id IS NULL "
            "AND conversation_id IS NULL AND element_id IS NULL AND draft_version_id IS NULL) OR "
            "(source_type = 'draft_version' AND draft_version_id IS NOT NULL AND review_decision_id IS NULL "
            "AND conversation_id IS NULL AND element_id IS NULL AND document_id IS NULL)",
            name="ck_memory_provenance_link_exclusive_target",
        ),
    )

    link_id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("memory_records.record_id"), nullable=False)
    source_type: Mapped[MemoryProvenanceSourceType] = mapped_column(
        _enum_column(MemoryProvenanceSourceType, 32), nullable=False
    )
    review_decision_id: Mapped[int | None] = mapped_column(ForeignKey("review_decisions.decision_id"), nullable=True)
    conversation_id: Mapped[int | None] = mapped_column(nullable=True)
    element_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_elements.element_id"), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("research_documents.document_id"), nullable=True)
    draft_version_id: Mapped[int | None] = mapped_column(ForeignKey("draft_versions.version_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
