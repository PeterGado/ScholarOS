from app.core.exceptions import ScholarOSError


class WritingDomainError(ScholarOSError):
    """Base class for Writing domain errors."""


class InvalidContextAssemblyInputError(WritingDomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Context assembly input is invalid: {reason}.")


class InvalidDraftTitleError(WritingDomainError):
    def __init__(self) -> None:
        super().__init__("Draft title must not be blank.")


class InvalidDraftVersionContentError(WritingDomainError):
    def __init__(self) -> None:
        super().__init__("Draft Version content must not be blank.")


class InvalidDraftVersionNumberError(WritingDomainError):
    def __init__(self, *, version_number: int) -> None:
        super().__init__(
            f"Draft Version version_number must be a positive integer, got {version_number}.")
        self.version_number = version_number


class InvalidWritingProfileNameError(WritingDomainError):
    def __init__(self) -> None:
        super().__init__("Writing Profile name must not be blank.")


class InvalidProfileCharacteristicSignalError(WritingDomainError):
    def __init__(self) -> None:
        super().__init__("Profile Characteristic signal must not be blank.")


class InvalidMemoryRecordContentError(WritingDomainError):
    def __init__(self) -> None:
        super().__init__("Memory Record content must not be blank.")


class DraftEvidenceLinkTargetError(WritingDomainError):
    """04_Logical_Data_Model.md §4.2 exclusive-arc rule: exactly one of chunk_id / document_id
    must be set, consistent with target_type.
    """

    def __init__(self) -> None:
        super().__init__(
            "Draft Evidence Link must set exactly one of chunk_id / document_id, consistent with target_type."
        )


class MemoryProvenanceLinkTargetError(WritingDomainError):
    """04_Logical_Data_Model.md §4.3 exclusive-arc rule: exactly one of the five target
    references must be set, consistent with source_type.
    """

    def __init__(self) -> None:
        super().__init__(
            "Memory Provenance Link must set exactly one target reference, consistent with source_type."
        )


class DraftNotFoundError(WritingDomainError):
    def __init__(self, *, draft_id: int) -> None:
        super().__init__(f"Draft {draft_id} was not found.")
        self.draft_id = draft_id


class StyleExtractionError(WritingDomainError):
    """The AI provider's response could not be parsed into valid Profile Characteristics -
    not valid JSON, missing a required field, or `characteristic_type` outside the frozen
    five-value enum (04_Logical_Data_Model.md §3.12). Never coerces an invalid value into a
    guessed one, mirroring app.modules.knowledge.domain.exceptions.SemanticExtractionError's
    own discipline.
    """

    def __init__(self, *, reason: str) -> None:
        super().__init__(f"Style extraction failed: {reason}")


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
