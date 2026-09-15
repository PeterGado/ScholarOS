import enum


class DraftStatus(str, enum.Enum):
    """04_Logical_Data_Model.md §3.15. Documented transitions only
    (05_Constraints_and_Integrity.md §"State Transitions"): drafting -> in_review;
    in_review -> drafting (revision requested); in_review -> approved; draft -> superseded.
    """

    DRAFTING = "drafting"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class CreatedBy(str, enum.Enum):
    """Shared "system / user" provenance value set for Draft Version, Draft Evidence Link, and
    Memory Record (04_Logical_Data_Model.md §3.16, §4.2, §3.8). Scoped to this module, not
    imported from app.modules.knowledge.domain.enums, to keep Writing's bounded context
    independent (ADR-003) even though the value set happens to match.
    """

    SYSTEM = "system"
    USER = "user"


class ReviewStatus(str, enum.Enum):
    OPEN = "open"
    DECIDED = "decided"


class ReviewOutcome(str, enum.Enum):
    APPROVED = "approved"
    REVISIONS_REQUESTED = "revisions_requested"
    REJECTED = "rejected"


class DraftEvidenceTargetType(str, enum.Enum):
    KNOWLEDGE_CHUNK = "knowledge_chunk"
    RESEARCH_DOCUMENT = "research_document"


class WritingProfileStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ProfileCharacteristicType(str, enum.Enum):
    STRUCTURE = "structure"
    VOCABULARY = "vocabulary"
    TRANSITIONS = "transitions"
    EXPLANATION = "explanation"
    CITATION = "citation"


class MemoryRecordType(str, enum.Enum):
    OBJECTIVE = "objective"
    HYPOTHESIS = "hypothesis"
    METHOD = "method"
    DECISION = "decision"
    TERMINOLOGY = "terminology"
    GUIDANCE = "guidance"
    OTHER = "other"


class MemoryRecordStatus(str, enum.Enum):
    CURRENT = "current"
    SUPERSEDED = "superseded"


class MemoryProvenanceSourceType(str, enum.Enum):
    USER_INPUT = "user_input"
    REVIEW_DECISION = "review_decision"
    CONVERSATION = "conversation"
    KNOWLEDGE_ELEMENT = "knowledge_element"
    DOCUMENT = "document"
    DRAFT_VERSION = "draft_version"


class ConversationStatus(str, enum.Enum):
    """04_Logical_Data_Model.md §3.9."""

    ACTIVE = "active"
    SUMMARIZED = "summarized"
    RETAINED = "retained"


class MessageDirection(str, enum.Enum):
    """04_Logical_Data_Model.md §3.10."""

    USER_REQUEST = "user_request"
    SYSTEM_RESPONSE = "system_response"


class MessageContextTargetType(str, enum.Enum):
    """04_Logical_Data_Model.md §4.4."""

    RESEARCH_DOCUMENT = "research_document"
    KNOWLEDGE_ELEMENT = "knowledge_element"
    KNOWLEDGE_CHUNK = "knowledge_chunk"
    DRAFT_VERSION = "draft_version"
    MEMORY_RECORD = "memory_record"
