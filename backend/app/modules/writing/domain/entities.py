from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.modules.writing.domain.enums import (
    ConversationStatus,
    CreatedBy,
    DraftEvidenceTargetType,
    DraftStatus,
    MemoryProvenanceSourceType,
    MemoryRecordStatus,
    MemoryRecordType,
    MessageContextTargetType,
    MessageDirection,
    ProfileCharacteristicType,
    ReviewOutcome,
    ReviewStatus,
    WritingProfileStatus,
)
from app.modules.writing.domain.exceptions import (
    DraftEvidenceLinkTargetError,
    InvalidDraftTitleError,
    InvalidDraftVersionContentError,
    InvalidDraftVersionNumberError,
    InvalidMemoryRecordContentError,
    InvalidMessageContentError,
    InvalidMessageSequenceError,
    InvalidProfileCharacteristicSignalError,
    InvalidWritingProfileNameError,
    MemoryProvenanceLinkTargetError,
    MessageContextLinkTargetError,
)


@dataclass
class Draft:
    """The stable writing-workspace object: identity, topic-scoped title/target, and lifecycle
    status (04_Logical_Data_Model.md §3.15; DR-016 to DR-019). Agent-scoped directly, not
    Project-scoped (ADR-009) - mirrors Knowledge/Memory/Conversation/Writing Profile.

    Deliberately carries no `current_version_id` - the current version is the latest
    `DraftVersion.version_number` for this draft, a derived value, never a stored attribute
    (04_Logical_Data_Model.md §6, normalization rationale #3).
    """

    agent_id: int
    title: str
    draft_id: int | None = None
    target: str | None = None
    status: DraftStatus = DraftStatus.DRAFTING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise InvalidDraftTitleError()

    @classmethod
    def create(cls, *, agent_id: int, title: str, target: str | None = None) -> "Draft":
        return cls(agent_id=agent_id, title=title, target=target)


@dataclass
class DraftVersion:
    """An immutable state of a Draft produced by one writing or revision cycle
    (04_Logical_Data_Model.md §3.16; DR-017; MVP-021; AIR-035). Content is never modified
    after creation - no method here exposes changing it (05_Constraints_and_Integrity.md
    invariant 4).
    """

    draft_id: int
    version_number: int
    content: str
    version_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: CreatedBy = CreatedBy.SYSTEM

    def __post_init__(self) -> None:
        if not self.content or not self.content.strip():
            raise InvalidDraftVersionContentError()
        if self.version_number < 1:
            raise InvalidDraftVersionNumberError(version_number=self.version_number)


@dataclass
class Review:
    """An evaluation round applied to a Draft Version (04_Logical_Data_Model.md §3.17;
    DR-019; WR-022 to WR-025). At most one open Review per Draft Version
    (05_Constraints_and_Integrity.md invariant 7) - enforced at the database layer
    (infrastructure/models.py partial unique index), not re-implemented here.
    """

    draft_version_id: int
    review_id: int | None = None
    status: ReviewStatus = ReviewStatus.OPEN
    notes: str | None = None
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None


@dataclass
class ReviewDecision:
    """The recorded outcome of a Review, preserved for audit
    (04_Logical_Data_Model.md §3.18; DR-019; AIR-054; MVP-018 to MVP-020). Immutable once
    created (05_Constraints_and_Integrity.md invariant 4); at most one decision per review
    (invariant 7), enforced at the database layer via a unique constraint on review_id.
    """

    review_id: int
    outcome: ReviewOutcome
    decided_by: int
    decision_id: int | None = None
    rationale: str | None = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DraftEvidenceLink:
    """Evidence annotation connecting a Draft Version to the Knowledge Chunk or Research
    Document that supports it (04_Logical_Data_Model.md §4.2; DR-018; AIR-027). Immutable and
    non-cascading once created (05_Constraints_and_Integrity.md line 199).

    Exactly one of `chunk_id` / `document_id` is set, consistent with `target_type`
    (exclusive arc) - validated here and re-enforced by a database CHECK constraint
    (infrastructure/models.py) for defense in depth.
    """

    draft_version_id: int
    target_type: DraftEvidenceTargetType
    link_id: int | None = None
    chunk_id: int | None = None
    document_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: CreatedBy = CreatedBy.SYSTEM

    def __post_init__(self) -> None:
        targets_set = sum(1 for value in (self.chunk_id, self.document_id) if value is not None)
        if targets_set != 1:
            raise DraftEvidenceLinkTargetError()
        if self.target_type == DraftEvidenceTargetType.KNOWLEDGE_CHUNK and self.chunk_id is None:
            raise DraftEvidenceLinkTargetError()
        if self.target_type == DraftEvidenceTargetType.RESEARCH_DOCUMENT and self.document_id is None:
            raise DraftEvidenceLinkTargetError()

    @classmethod
    def for_knowledge_chunk(
        cls, *, draft_version_id: int, chunk_id: int, created_by: CreatedBy = CreatedBy.SYSTEM
    ) -> "DraftEvidenceLink":
        return cls(
            draft_version_id=draft_version_id,
            target_type=DraftEvidenceTargetType.KNOWLEDGE_CHUNK,
            chunk_id=chunk_id,
            created_by=created_by,
        )

    @classmethod
    def for_research_document(
        cls, *, draft_version_id: int, document_id: int, created_by: CreatedBy = CreatedBy.SYSTEM
    ) -> "DraftEvidenceLink":
        return cls(
            draft_version_id=draft_version_id,
            target_type=DraftEvidenceTargetType.RESEARCH_DOCUMENT,
            document_id=document_id,
            created_by=created_by,
        )


@dataclass
class WritingProfile:
    """The author's preserved writing characteristics (04_Logical_Data_Model.md §3.11;
    DR-010 to DR-012). Agent-scoped directly (ADR-009). At most one active profile per Agent
    (05_Constraints_and_Integrity.md invariant 8), enforced at the database layer.
    """

    agent_id: int
    user_id: int
    name: str
    profile_id: int | None = None
    status: WritingProfileStatus = WritingProfileStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise InvalidWritingProfileNameError()


@dataclass
class ProfileCharacteristic:
    """A single preserved stylistic attribute (04_Logical_Data_Model.md §3.12; DR-010, DR-012).
    Structurally distinct from Knowledge/evidence entities - never a valid Draft Evidence Link
    target (05_Constraints_and_Integrity.md §"Evidence"; Stage 1 plan §5.B).
    """

    profile_id: int
    characteristic_type: ProfileCharacteristicType
    signal: str
    characteristic_id: int | None = None
    confidence: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.signal or not self.signal.strip():
            raise InvalidProfileCharacteristicSignalError()


@dataclass
class ProfileCharacteristicSource:
    """Provenance of a Profile Characteristic to the authored sample that informed it
    (04_Logical_Data_Model.md §4.5; DR-012).
    """

    characteristic_id: int
    document_id: int
    link_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MemoryRecord:
    """Persistent project context and decision history with supersession
    (04_Logical_Data_Model.md §3.8; DR-013 to DR-015). Agent-scoped directly (ADR-009).

    Populated only through user input or approved outcomes - the system never infers memory
    without user awareness (MVP-011; 05_Constraints_and_Integrity.md invariant 11). This
    entity only models the persisted shape; no automatic-memory-creation logic exists in
    Stage 2 (Stage 1 plan §8, §19.5 - deferred to the generation/review stages that can
    supply genuine user-awareness signals).
    """

    agent_id: int
    record_type: MemoryRecordType
    content: str
    record_id: int | None = None
    rationale: str | None = None
    status: MemoryRecordStatus = MemoryRecordStatus.CURRENT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: CreatedBy = CreatedBy.USER
    superseded_record_id: int | None = None
    superseded_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.content or not self.content.strip():
            raise InvalidMemoryRecordContentError()


@dataclass
class MemoryProvenanceLink:
    """Traces a Memory Record to the artifact or activity that produced it
    (04_Logical_Data_Model.md §4.3; DR-015).

    Exactly one of the five target references is set, consistent with `source_type`, for every
    source_type except `user_input` - which by definition names no separate linkable artifact
    (the Memory Record was established directly from what the user said, not derived from
    another entity) and so carries zero target references. This reads `04_Logical_Data_Model.md`
    §4.3's "exactly one target reference is set" as scoped to the five source types that have a
    matching column; `user_input` is the sixth enumerated value with no corresponding column,
    which this implementation treats as "no reference to set" rather than a modeling
    contradiction. Flagged as an implementation interpretation, not a frozen-model change
    (Stage 2 completion report §13).

    `conversation_id` carries a real foreign key as of the instructions-contract resolution
    below (Project_Writing_Implementation_Plan.md §19 item 3 follow-up): Stage 2 deferred
    Conversation entirely (Stage 2 prompt §40), so this column originally had none; Conversation
    now exists (see `Conversation`/`Message`/`MessageContextLink` below), so source_type=
    conversation is usable end-to-end.
    """

    record_id: int
    source_type: MemoryProvenanceSourceType
    link_id: int | None = None
    review_decision_id: int | None = None
    conversation_id: int | None = None
    element_id: int | None = None
    document_id: int | None = None
    draft_version_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        targets = (
            self.review_decision_id,
            self.conversation_id,
            self.element_id,
            self.document_id,
            self.draft_version_id,
        )
        targets_set = sum(1 for value in targets if value is not None)

        if self.source_type == MemoryProvenanceSourceType.USER_INPUT:
            if targets_set != 0:
                raise MemoryProvenanceLinkTargetError()
            return

        if targets_set != 1:
            raise MemoryProvenanceLinkTargetError()

        expected = {
            MemoryProvenanceSourceType.REVIEW_DECISION: self.review_decision_id,
            MemoryProvenanceSourceType.CONVERSATION: self.conversation_id,
            MemoryProvenanceSourceType.KNOWLEDGE_ELEMENT: self.element_id,
            MemoryProvenanceSourceType.DOCUMENT: self.document_id,
            MemoryProvenanceSourceType.DRAFT_VERSION: self.draft_version_id,
        }
        if expected[self.source_type] is None:
            raise MemoryProvenanceLinkTargetError()


@dataclass
class Conversation:
    """Project-scoped interaction history (04_Logical_Data_Model.md §3.9; WR-034). Agent-scoped
    directly (ADR-009).

    Realizes Stage 1 plan §19 item 3's decision - use the existing frozen Conversation/Message
    entities to carry per-request Draft generation instructions, rather than inventing a new
    field on Draft or ContextAssemblyInput. Deferred out of Stage 2 (Stage 2 prompt §40);
    implemented resolving the Stage 8 validation finding that the decision had never actually
    been realized (Stage 7 shipped a plain `instructions` string instead).

    `title` doubles as the association key `RequestDraftGenerationUseCase` uses to find-or-
    create "the Conversation for Draft N" (see that use case's docstring) - a deliberate reuse
    of the frozen, genuinely free-form "Optional conversation label" field rather than adding a
    `draft_id` column, which would modify the frozen Conversation shape.
    """

    agent_id: int
    conversation_id: int | None = None
    title: str | None = None
    status: ConversationStatus = ConversationStatus.ACTIVE
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    summarized_at: datetime | None = None
    deleted_at: datetime | None = None


@dataclass
class Message:
    """An individual exchange within a Conversation (04_Logical_Data_Model.md §3.10; AIR-006).
    Ordered within its Conversation by `sequence`, strictly ascending from 1
    (candidate key `(conversation_id, sequence)`).
    """

    conversation_id: int
    sequence: int
    direction: MessageDirection
    content: str
    message_id: int | None = None
    origin: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.content or not self.content.strip():
            raise InvalidMessageContentError()
        if self.sequence < 1:
            raise InvalidMessageSequenceError(sequence=self.sequence)


@dataclass
class MessageContextLink:
    """Reference from a Message to the project artifact it concerns
    (04_Logical_Data_Model.md §4.4). Exactly one of the five target references is set,
    consistent with `target_type` (exclusive arc) - same discipline as Draft Evidence Link and
    Memory Provenance Link above.

    First real use: linking a generation-request instructions Message (and the system's own
    response Message) to the Draft Version it produced (`app/workers/executor.py`), closing the
    provenance gap between "what was asked for" and "what was generated."
    """

    message_id: int
    target_type: MessageContextTargetType
    link_id: int | None = None
    document_id: int | None = None
    element_id: int | None = None
    chunk_id: int | None = None
    draft_version_id: int | None = None
    memory_record_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        targets = (
            self.document_id,
            self.element_id,
            self.chunk_id,
            self.draft_version_id,
            self.memory_record_id,
        )
        targets_set = sum(1 for value in targets if value is not None)
        if targets_set != 1:
            raise MessageContextLinkTargetError()

        expected = {
            MessageContextTargetType.RESEARCH_DOCUMENT: self.document_id,
            MessageContextTargetType.KNOWLEDGE_ELEMENT: self.element_id,
            MessageContextTargetType.KNOWLEDGE_CHUNK: self.chunk_id,
            MessageContextTargetType.DRAFT_VERSION: self.draft_version_id,
            MessageContextTargetType.MEMORY_RECORD: self.memory_record_id,
        }
        if expected[self.target_type] is None:
            raise MessageContextLinkTargetError()
