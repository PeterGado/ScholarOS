from enum import Enum


class DocumentProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class DocumentPurpose(str, Enum):
    """Resolves a gap Stage 3/4 explicitly flagged and deferred (see
    `UploadWritingStyleDocumentUseCase`/`ExtractWritingStyleProfileUseCase`'s own docstrings,
    "Stage 3's own completion report, Risk #1"): the frozen Logical Data Model has no field
    distinguishing a writing-style sample from ordinary research material - both reuse the
    same `ResearchDocument` row. Left unresolved, a style sample (which the knowledge pipeline
    never processes by design) sits forever at `processing_status=pending` on the Research
    Documents list with no explanation, and the Writing Style page has no way to show what a
    user already uploaded across sessions. A real user-facing bug, not a hypothetical - this is
    the deviation that resolves it, recorded here rather than silently added.
    """

    RESEARCH = "research"
    WRITING_STYLE_SAMPLE = "writing_style_sample"
