from dataclasses import dataclass, field
from datetime import datetime, timezone

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
from app.modules.writing.domain.exceptions import (
    InvalidMemoryRecordContentError,
    InvalidMessageContentError,
    InvalidMessageSequenceError,
    InvalidProfileCharacteristicSignalError,
    InvalidWritingProfileNameError,
    MemoryProvenanceLinkTargetError,
    MessageContextLinkTargetError,
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
    """A single preserved stylistic attribute (04_Logical_Data_Model.md §3.12; DR-010, DR-012)."""

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

    Exactly one of the target references is set, consistent with `source_type`, for every
    source_type except `user_input` - which by definition names no separate linkable artifact
    (the Memory Record was established directly from what the user said, not derived from
    another entity) and so carries zero target references.

    Deviation from the frozen model: `review_decision_id`/`draft_version_id` and their matching
    `MemoryProvenanceSourceType` values were removed along with the Drafts/Review pipeline
    (see that enum's docstring) - recorded in docs/Project_Writing_Implementation_Plan.md.
    `conversation_id` is now Memory's only automatic-generation source.
    """

    record_id: int
    source_type: MemoryProvenanceSourceType
    link_id: int | None = None
    conversation_id: int | None = None
    element_id: int | None = None
    document_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        targets = (self.conversation_id, self.element_id, self.document_id)
        targets_set = sum(1 for value in targets if value is not None)

        if self.source_type == MemoryProvenanceSourceType.USER_INPUT:
            if targets_set != 0:
                raise MemoryProvenanceLinkTargetError()
            return

        if targets_set != 1:
            raise MemoryProvenanceLinkTargetError()

        expected = {
            MemoryProvenanceSourceType.CONVERSATION: self.conversation_id,
            MemoryProvenanceSourceType.KNOWLEDGE_ELEMENT: self.element_id,
            MemoryProvenanceSourceType.DOCUMENT: self.document_id,
        }
        if expected[self.source_type] is None:
            raise MemoryProvenanceLinkTargetError()


@dataclass
class Conversation:
    """Project-scoped interaction history (04_Logical_Data_Model.md §3.9; WR-034). Agent-scoped
    directly (ADR-009). The Agent Workspace chat surface (Persistent Brain Decision 3) - `title`
    is a genuinely free-form, optional conversation label.
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
    (04_Logical_Data_Model.md §4.4). Exactly one of the target references is set, consistent
    with `target_type` (exclusive arc) - same discipline as Memory Provenance Link above.

    Deviation from the frozen model: `draft_version_id` and its matching
    `MessageContextTargetType` value were removed along with the Drafts/Review pipeline (see
    `MemoryProvenanceSourceType`'s docstring) - recorded in
    docs/Project_Writing_Implementation_Plan.md.
    """

    message_id: int
    target_type: MessageContextTargetType
    link_id: int | None = None
    document_id: int | None = None
    element_id: int | None = None
    chunk_id: int | None = None
    memory_record_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        targets = (self.document_id, self.element_id, self.chunk_id, self.memory_record_id)
        targets_set = sum(1 for value in targets if value is not None)
        if targets_set != 1:
            raise MessageContextLinkTargetError()

        expected = {
            MessageContextTargetType.RESEARCH_DOCUMENT: self.document_id,
            MessageContextTargetType.KNOWLEDGE_ELEMENT: self.element_id,
            MessageContextTargetType.KNOWLEDGE_CHUNK: self.chunk_id,
            MessageContextTargetType.MEMORY_RECORD: self.memory_record_id,
        }
        if expected[self.target_type] is None:
            raise MessageContextLinkTargetError()
