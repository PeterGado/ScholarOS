class ScholarOSError(Exception):
    """Base class for all application-raised errors. Modules define their own subclasses."""


class UploadTooLargeError(ScholarOSError):
    """Raised by any file-upload route (research documents, writing-style samples) when the
    uploaded content exceeds Settings.max_upload_size_bytes. A cross-cutting API-boundary
    concern shared by two modules, not owned by either - lives here rather than under a single
    module's own exceptions, mirroring how it's caught at the route layer (app.core.uploads),
    not inside either module's use case.
    """

    def __init__(self, *, max_bytes: int) -> None:
        super().__init__(f"Uploaded file exceeds the maximum allowed size of {max_bytes} bytes.")
        self.max_bytes = max_bytes


class UnsupportedUploadFormatError(ScholarOSError):
    """Raised by any file-upload route (research documents, writing-style samples) when the
    uploaded content isn't recognized as plain text, .docx, or PDF (app.core.document_formats)
    - the only formats the Knowledge Processing Pipeline can ever extract text from. Same
    cross-cutting rationale as UploadTooLargeError: shared by two modules, not owned by either.
    """

    def __init__(self) -> None:
        super().__init__("Unsupported file format. Only plain text, .docx, and PDF are supported.")


class MaliciousUploadError(ScholarOSError):
    """Raised by any file-upload route (research documents, writing-style samples) when
    `app.core.virus_scan.is_known_malicious` confirms the uploaded content's hash matches a
    file VirusTotal already has a multi-engine malicious verdict for (2026-10-11,
    production-readiness pass). Only ever raised when `virustotal_api_key` is configured - see
    that setting's own docstring for the "missing config disables the feature" shape every
    optional integration in this app uses.
    """

    def __init__(self) -> None:
        super().__init__("This file matches a known malicious file and cannot be uploaded.")
