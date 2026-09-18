from app.core.exceptions import ScholarOSError


class WritingDomainError(ScholarOSError):
    """Base class for Writing domain errors."""


class InvalidContextAssemblyInputError(WritingDomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Context assembly input is invalid: {reason}.")


class InvalidWritingProfileNameError(WritingDomainError):
    def __init__(self) -> None:
        super().__init__("Writing Profile name must not be blank.")


class InvalidProfileCharacteristicSignalError(WritingDomainError):
    def __init__(self) -> None:
        super().__init__("Profile Characteristic signal must not be blank.")


class InvalidMemoryRecordContentError(WritingDomainError):
    def __init__(self) -> None:
        super().__init__("Memory Record content must not be blank.")


class MemoryProvenanceLinkTargetError(WritingDomainError):
    """04_Logical_Data_Model.md §4.3 exclusive-arc rule: exactly one of the five target
    references must be set, consistent with source_type.
    """

    def __init__(self) -> None:
        super().__init__(
            "Memory Provenance Link must set exactly one target reference, consistent with source_type."
        )


class MemoryRecordNotFoundError(WritingDomainError):
    """Also raised (non-enumeration) when a Memory Record exists but belongs to a different
    Agent.
    """

    def __init__(self, *, record_id: int) -> None:
        super().__init__(f"Memory Record {record_id} was not found.")
        self.record_id = record_id


class MemoryRecordAlreadySupersededError(WritingDomainError):
    """Only a `current` Memory Record can be superseded - re-superseding an already-superseded
    one would silently orphan the supersession chain (05_Constraints_and_Integrity.md's
    supersession pattern, mirrored from Knowledge Element's own).
    """

    def __init__(self, *, record_id: int) -> None:
        super().__init__(f"Memory Record {record_id} has already been superseded.")
        self.record_id = record_id


class ConversationNotFoundError(WritingDomainError):
    """Also raised (non-enumeration) when a Conversation exists but belongs to a different
    Agent.
    """

    def __init__(self, *, conversation_id: int) -> None:
        super().__init__(f"Conversation {conversation_id} was not found.")
        self.conversation_id = conversation_id


class WritingProfileNotFoundError(WritingDomainError):
    """The Agent has no active Writing Profile yet - a normal pre-Stage-3 state (no style
    sample has ever been uploaded), not an ownership violation.
    """

    def __init__(self, *, agent_id: int) -> None:
        super().__init__(f"Agent {agent_id} has no active Writing Profile yet.")
        self.agent_id = agent_id


class EmptyGeneratedContentError(WritingDomainError):
    def __init__(self) -> None:
        super().__init__("The generation provider returned empty content.")


class StyleExtractionError(WritingDomainError):
    """The AI provider's response could not be parsed into valid Profile Characteristics -
    not valid JSON, missing a required field, or `characteristic_type` outside the frozen
    five-value enum (04_Logical_Data_Model.md §3.12). Never coerces an invalid value into a
    guessed one, mirroring app.modules.knowledge.domain.exceptions.SemanticExtractionError's
    own discipline.
    """

    def __init__(self, *, reason: str) -> None:
        super().__init__(f"Style extraction failed: {reason}")


class TooManyWritingStyleSamplesError(WritingDomainError):
    """An Agent may hold at most `style_ingestion.MAX_WRITING_STYLE_SAMPLES` writing-style
    samples at once - extraction never looks at more than that many per run regardless, so
    allowing more uploads would only let samples pile up that can never actually be used.
    """

    def __init__(self, *, limit: int) -> None:
        super().__init__(
            f"You already have the maximum of {limit} writing style samples. "
            "Delete one before uploading another."
        )
        self.limit = limit


class NoUsableWritingStyleSamplesError(WritingDomainError):
    """Raised when extraction is requested with no document_ids at all - Stage 4 must not
    create an empty Writing Profile simply because the use case was called (Stage 4 prompt §17).
    """

    def __init__(self) -> None:
        super().__init__("At least one writing-style sample document must be supplied for extraction.")


class InvalidStyleSampleReferenceError(WritingDomainError):
    """A supplied document_id does not exist, or does not belong to the authenticated user's
    own Project - deliberately indistinguishable (non-enumeration), mirroring
    ProjectNotFoundError's own established precedent for ownership-mismatch-vs-missing.
    """

    def __init__(self, *, document_id: int) -> None:
        super().__init__(
            f"Research Document {document_id} is not a usable writing-style sample for this Agent.")
        self.document_id = document_id


class UnusableWritingStyleSampleError(WritingDomainError):
    """The referenced document's stored content could not be decoded as text, or decoded to
    nothing meaningful - mirrors app.modules.knowledge.domain.text_extraction's own strict
    UTF-8-or-unsupported approach (duplicated deliberately, not imported - see
    domain/style_extraction.py's module docstring for why).
    """

    def __init__(self, *, document_id: int) -> None:
        super().__init__(
            f"Research Document {document_id}'s stored content could not be used as a writing sample.")
        self.document_id = document_id


class MissingStoredStyleSampleError(WritingDomainError):
    """The Research Document row exists but its referenced object-store content does not -
    mirrors app.modules.knowledge.domain.exceptions.MissingStoredContentError's own failure
    mode and deliberately-unregistered (falls through to the generic 400 handler) precedent.
    """

    def __init__(self, *, document_id: int) -> None:
        super().__init__(
            f"Research Document {document_id}'s stored content was not found.")
        self.document_id = document_id


class InvalidMessageContentError(WritingDomainError):
    def __init__(self) -> None:
        super().__init__("Message content must not be blank.")


class InvalidMessageSequenceError(WritingDomainError):
    def __init__(self, *, sequence: int) -> None:
        super().__init__(f"Message sequence must be a positive integer, got {sequence}.")
        self.sequence = sequence


class MessageContextLinkTargetError(WritingDomainError):
    """04_Logical_Data_Model.md §4.4 exclusive-arc rule: exactly one of the five target
    references must be set, consistent with target_type.
    """

    def __init__(self) -> None:
        super().__init__(
            "Message Context Link must set exactly one target reference, consistent with target_type."
        )


class MemoryExtractionError(WritingDomainError):
    """The AI provider's response could not be parsed into a valid Memory Record - mirrors
    `StyleExtractionError`'s own discipline exactly (invalid JSON, missing field, or
    `record_type` outside the frozen `MemoryRecordType` enum). Raised from within chat reply
    generation (the Work Item worker), swallowed there exactly like conversation summarization's
    own failure handling - a bad extraction never turns an otherwise-successful chat reply into
    a failed Work Item.
    """

    def __init__(self, *, reason: str) -> None:
        super().__init__(f"Memory extraction failed: {reason}")


class ChatReplyWorkItemNotFoundError(WritingDomainError):
    """No such Work Item, or its payload_reference doesn't actually belong to the Conversation
    the caller named - deliberately indistinguishable (non-enumeration), mirroring
    ConversationNotFoundError's own established precedent. Closes a real cross-conversation
    probing risk: without this check, an authenticated owner of *some* conversation could poll
    any work_item_id and read another conversation's generation status/error text.
    """

    def __init__(self, *, work_item_id: int) -> None:
        super().__init__(f"Chat reply Work Item {work_item_id} was not found.")
        self.work_item_id = work_item_id


class ChatReplyCannotBeRetriedError(WritingDomainError):
    """Only a terminally `failed` Work Item can be retried - one still `queued`/`running` has a
    live attempt in flight, and one `succeeded` already produced its reply Message. Mirrors
    DocumentCannotBeRetriedError's own status-gating exactly.
    """

    def __init__(self, *, work_item_id: int, state: str) -> None:
        super().__init__(f"Chat reply Work Item {work_item_id} cannot be retried (current state: {state}).")
        self.work_item_id = work_item_id
        self.state = state


class WritingProfileAlreadyExtractedError(WritingDomainError):
    """Stage 4 prompt §12/§13: the frozen model provides no update/regeneration mechanism for
    Profile Characteristic (05_Constraints_and_Integrity.md: no status column, no
    superseded_id, and explicitly "never tombstoned" - so neither accumulation nor deletion is
    a safe silent default). Rather than silently choosing a persistence strategy, re-running
    extraction against a profile that already has characteristics is refused outright until
    the project owner decides the intended regeneration semantics (Stage 4 completion report,
    §Deviations/§Open Items).
    """

    def __init__(self, *, profile_id: int) -> None:
        super().__init__(
            f"Writing Profile {profile_id} already has extracted characteristics; "
            "re-extraction is not yet supported (regeneration semantics are undecided - see Stage 4 report)."
        )
        self.profile_id = profile_id
