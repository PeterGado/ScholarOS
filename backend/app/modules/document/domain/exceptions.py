from app.core.exceptions import ScholarOSError


class DocumentDomainError(ScholarOSError):
    """Base class for Research Document domain errors."""


class InvalidDocumentTitleError(DocumentDomainError):
    def __init__(self) -> None:
        super().__init__("Document title must be a non-empty string.")


class InvalidDocumentFormatError(DocumentDomainError):
    def __init__(self) -> None:
        super().__init__("Document format must be a non-empty string.")


class EmptyDocumentContentError(DocumentDomainError):
    def __init__(self) -> None:
        super().__init__("Document content must not be empty.")


class ResearchDocumentNotFoundError(DocumentDomainError):
    def __init__(self, *, document_id: int) -> None:
        super().__init__(f"Research Document not found (document_id={document_id}).")
        self.document_id = document_id


class TooManyResearchDocumentsError(DocumentDomainError):
    """A Project may hold at most `MAX_RESEARCH_DOCUMENTS_PER_PROJECT` (see
    UploadResearchDocumentUseCase) research documents at once - a deliberate cap, not an
    incidental limitation: each document costs real AI provider calls to process, and an
    unbounded project could exhaust a free-tier daily quota (or run up a paid one) on its own.
    """

    def __init__(self, *, project_id: int, limit: int) -> None:
        super().__init__(
            f"Project {project_id} already has the maximum of {limit} research documents. "
            "Delete one before uploading another."
        )
        self.project_id = project_id
        self.limit = limit


class DocumentCannotBeRetriedError(DocumentDomainError):
    """Retrying only makes sense for a document whose processing has terminally `failed` -
    mirrors `DocumentCannotBeDeletedError`'s own status-gated pattern.
    """

    def __init__(self, *, document_id: int, processing_status: str) -> None:
        super().__init__(
            f"Research Document {document_id} cannot be retried while its processing status "
            f"is {processing_status!r}."
        )
        self.document_id = document_id
        self.processing_status = processing_status


class DocumentCannotBeDeletedError(DocumentDomainError):
    """A Research Document may only be deleted before it has been successfully processed -
    once its knowledge has been extracted, it becomes a permanent part of the Agent's
    knowledge base and is no longer a manageable "file" (product decision: processed
    documents have no delete affordance in the UI at all, enforced here too so the rule holds
    even for a direct API call).
    """

    def __init__(self, *, document_id: int, processing_status: str) -> None:
        super().__init__(
            f"Research Document {document_id} cannot be deleted while its processing status "
            f"is {processing_status!r}."
        )
        self.document_id = document_id
        self.processing_status = processing_status
