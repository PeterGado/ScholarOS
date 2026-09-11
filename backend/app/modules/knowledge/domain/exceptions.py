from app.core.exceptions import ScholarOSError


class KnowledgeDomainError(ScholarOSError):
    """Base class for Knowledge domain errors."""


class MissingStoredContentError(KnowledgeDomainError):
    """The Research Document row exists but its referenced object-store content does not
    (Backend_Slice2_Implementation_Plan.md; Stage 4 failure-mode: missing stored content).
    """

    def __init__(self, *, document_id: int, content_reference: str) -> None:
        super().__init__(f"Document {document_id}'s stored content ({content_reference}) was not found.")
        self.document_id = document_id
        self.content_reference = content_reference


class UnsupportedDocumentFormatError(KnowledgeDomainError):
    """Stage 4's mechanical extractor could not decode the document's content as text.
    Deliberately independent of `ResearchDocument.format` (an unconstrained string with no
    approved enumeration) - decodability, not the declared format label, is the test.
    """

    def __init__(self, *, document_id: int) -> None:
        super().__init__(f"Document {document_id}'s content could not be decoded as text.")
        self.document_id = document_id


class EmptyExtractedTextError(KnowledgeDomainError):
    """Extraction succeeded but produced no meaningful text after normalization."""

    def __init__(self, *, document_id: int) -> None:
        super().__init__(f"Document {document_id} produced no meaningful text after extraction.")
        self.document_id = document_id


class SemanticExtractionError(KnowledgeDomainError):
    """The AI provider's response could not be parsed into a valid Knowledge Element - not
    valid JSON, missing a required field, or `element_type` outside the frozen five-value
    enum (04_Logical_Data_Model.md §3.5). Never coerces an invalid value into a guessed one.
    """

    def __init__(self, *, reason: str) -> None:
        super().__init__(f"Semantic extraction failed: {reason}")


class AgentResolutionError(KnowledgeDomainError):
    """Defensive: a Research Document's Project has no resolvable owning Agent. Should never
    occur given the Agent-Project 1:1 permanent invariant (05_Constraints_and_Integrity.md
    invariant 15), but handled explicitly rather than surfacing as an unrelated AttributeError.
    """

    def __init__(self, *, document_id: int) -> None:
        super().__init__(f"Could not resolve the owning Agent for document {document_id}.")
        self.document_id = document_id
