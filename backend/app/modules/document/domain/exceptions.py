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
