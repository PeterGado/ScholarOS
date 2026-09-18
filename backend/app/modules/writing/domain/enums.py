import enum


class CreatedBy(str, enum.Enum):
    """Shared "system / user" provenance value set for Memory Record (04_Logical_Data_Model.md
    §3.8). Scoped to this module, not imported from app.modules.knowledge.domain.enums, to keep
    Writing's bounded context independent (ADR-003) even though the value set happens to match.
    """

    SYSTEM = "system"
    USER = "user"


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
    # Persistent Brain v3 audit fix: v2's memory extraction reused GUIDANCE for both generic
    # preferences and inferred style observations, with no way to tell which a persisted
    # record meant. STYLE is a dedicated value for the latter only - GUIDANCE reverts to its
    # original, generic sense. Extends the frozen enumerated family at
    # docs/database/04_Logical_Data_Model.md §3.8 - recorded as a deviation, not a silent
    # rewrite, in docs/Project_Writing_Implementation_Plan.md.
    STYLE = "style"
    OTHER = "other"


class MemoryRecordStatus(str, enum.Enum):
    CURRENT = "current"
    SUPERSEDED = "superseded"


class MemoryProvenanceSourceType(str, enum.Enum):
    """Deviation from the frozen enumerated family (04_Logical_Data_Model.md §4.3): dropped
    REVIEW_DECISION and DRAFT_VERSION when the Drafts/Review pipeline was removed entirely (the
    user only ever wants chat replies, not a separate generate-then-review document workflow -
    recorded in docs/Project_Writing_Implementation_Plan.md). CONVERSATION - already modeled
    but never wired to a real generator - is now Memory's only automatic source, triggered
    periodically from chat (see memory_extraction.MEMORY_EXTRACTION_TRIGGER_COUNT).
    """

    USER_INPUT = "user_input"
    CONVERSATION = "conversation"
    KNOWLEDGE_ELEMENT = "knowledge_element"
    DOCUMENT = "document"


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
    """04_Logical_Data_Model.md §4.4. Deviation: dropped DRAFT_VERSION along with the removed
    Drafts pipeline (see MemoryProvenanceSourceType's own docstring above)."""

    RESEARCH_DOCUMENT = "research_document"
    KNOWLEDGE_ELEMENT = "knowledge_element"
    KNOWLEDGE_CHUNK = "knowledge_chunk"
    MEMORY_RECORD = "memory_record"
