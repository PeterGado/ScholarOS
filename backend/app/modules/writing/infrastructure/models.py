from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Enum, Float, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.modules.writing.domain.enums import (
    ConversationStatus,
    CreatedBy,
    MemoryProvenanceSourceType,
    MemoryRecordStatus,
    MemoryRecordType,
    MessageContextTargetType,
    MessageDirection,
    ProfileCharacteristicType,
    WritingProfileStatus,
)

__all__ = [
    "WritingProfile",
    "ProfileCharacteristic",
    "ProfileCharacteristicSource",
    "MemoryRecord",
    "MemoryProvenanceLink",
    "Conversation",
    "Message",
    "MessageContextLink",
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
            # A real dialect-compatibility gap found during the Postgres migration (2026-09-18):
            # only sqlite_where was ever set. SQLAlchemy's partial-index `_where` kwargs are
            # dialect-namespaced - on Postgres, an index with only sqlite_where silently becomes
            # a *full* unique index (no WHERE clause at all), wrongly enforcing "at most one
            # WritingProfile per Agent ever" instead of invariant 8's actual rule ("at most one
            # *active* Writing Profile per Agent") - it would have rejected a second profile
            # after the first was deactivated, a real behavior difference between dialects.
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
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
    # 2026-09-21: real-traffic audit - filtered on every "list a Writing Profile's
    # characteristics" call, with no index at all before this.
    __table_args__ = (Index("ix_profile_characteristics_profile_id", "profile_id"),)

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
    # 2026-09-21: real-traffic audit - no new index needed here. The only real query against
    # this table filters by characteristic_id alone (list_by_characteristic_id), which is
    # already the leading column of the unique constraint below - Postgres can use a composite
    # index's leading column alone (the btree prefix rule) for that lookup.
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
    # 2026-09-21: real-traffic audit - runs on every chat reply's context assembly
    # (list_current_by_agent_id filters exactly agent_id + status), no index at all before this.
    __table_args__ = (Index("ix_memory_records_agent_id_status", "agent_id", "status"),)

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

    Deviation from the frozen model: `review_decision_id`/`draft_version_id` were dropped along
    with the Drafts/Review pipeline's removal (see the domain entity's docstring,
    domain/entities.py, and docs/Project_Writing_Implementation_Plan.md for the full
    reasoning). The CHECK constraint below encodes the same "user_input -> zero references,
    else exactly one" interpretation implemented in the domain layer, over the remaining
    reference columns.
    """

    __tablename__ = "memory_provenance_links"
    __table_args__ = (
        CheckConstraint(
            "(source_type = 'user_input' AND conversation_id IS NULL "
            "AND element_id IS NULL AND document_id IS NULL) OR "
            "(source_type = 'conversation' AND conversation_id IS NOT NULL "
            "AND element_id IS NULL AND document_id IS NULL) OR "
            "(source_type = 'knowledge_element' AND element_id IS NOT NULL "
            "AND conversation_id IS NULL AND document_id IS NULL) OR "
            "(source_type = 'document' AND document_id IS NOT NULL "
            "AND conversation_id IS NULL AND element_id IS NULL)",
            name="ck_memory_provenance_link_exclusive_target",
        ),
        # 2026-09-21: real-traffic audit - provenance lookup per Memory Record
        # (list_by_record_id), no index at all before this.
        Index("ix_memory_provenance_links_record_id", "record_id"),
    )

    link_id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("memory_records.record_id"), nullable=False)
    source_type: Mapped[MemoryProvenanceSourceType] = mapped_column(
        _enum_column(MemoryProvenanceSourceType, 32), nullable=False
    )
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.conversation_id"), nullable=True)
    element_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_elements.element_id"), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("research_documents.document_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)


class Conversation(Base):
    """Project-scoped interaction history (04_Logical_Data_Model.md §3.9; WR-034)."""

    __tablename__ = "conversations"
    # 2026-09-21: real-traffic audit - listing a user's conversations filters exactly
    # agent_id + deleted_at (ListConversationsUseCase), no index at all before this.
    __table_args__ = (Index("ix_conversations_agent_id_deleted_at", "agent_id", "deleted_at"),)

    conversation_id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.agent_id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(
        _enum_column(ConversationStatus, 16), nullable=False, default=ConversationStatus.ACTIVE
    )
    started_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    summarized_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Message(Base):
    """An individual exchange within a Conversation (04_Logical_Data_Model.md §3.10; AIR-006)."""

    __tablename__ = "messages"
    # 2026-09-21: real-traffic audit - no new index needed here. Every real query
    # (count_by_conversation_id/list_by_conversation_id) filters `WHERE conversation_id = ?`
    # alone, and conversation_id is already the leading column of the unique constraint below,
    # so the btree-prefix rule already serves it without a dedicated index.
    __table_args__ = (UniqueConstraint("conversation_id", "sequence", name="uq_message_conversation_sequence"),)

    message_id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.conversation_id"), nullable=False)
    sequence: Mapped[int] = mapped_column(nullable=False)
    direction: Mapped[MessageDirection] = mapped_column(_enum_column(MessageDirection, 16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)


class MessageContextLink(Base):
    """Reference from a Message to the project artifact it concerns
    (04_Logical_Data_Model.md §4.4). Exclusive-arc CHECK constraint mirrors Memory Provenance
    Link's own pattern above. Deviation from the frozen model: `draft_version_id` was dropped
    along with the Drafts/Review pipeline's removal (see MemoryProvenanceLink's docstring).
    """

    __tablename__ = "message_context_links"
    __table_args__ = (
        CheckConstraint(
            "(target_type = 'research_document' AND document_id IS NOT NULL AND element_id IS NULL "
            "AND chunk_id IS NULL AND memory_record_id IS NULL) OR "
            "(target_type = 'knowledge_element' AND element_id IS NOT NULL AND document_id IS NULL "
            "AND chunk_id IS NULL AND memory_record_id IS NULL) OR "
            "(target_type = 'knowledge_chunk' AND chunk_id IS NOT NULL AND document_id IS NULL "
            "AND element_id IS NULL AND memory_record_id IS NULL) OR "
            "(target_type = 'memory_record' AND memory_record_id IS NOT NULL AND document_id IS NULL "
            "AND element_id IS NULL AND chunk_id IS NULL)",
            name="ck_message_context_link_exclusive_target",
        ),
        # 2026-09-21: real-traffic audit - context-link lookup per message (list_by_message_id),
        # no index at all before this.
        Index("ix_message_context_links_message_id", "message_id"),
    )

    link_id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.message_id"), nullable=False)
    target_type: Mapped[MessageContextTargetType] = mapped_column(
        _enum_column(MessageContextTargetType, 32), nullable=False
    )
    document_id: Mapped[int | None] = mapped_column(ForeignKey("research_documents.document_id"), nullable=True)
    element_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_elements.element_id"), nullable=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_chunks.chunk_id"), nullable=True)
    memory_record_id: Mapped[int | None] = mapped_column(ForeignKey("memory_records.record_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
