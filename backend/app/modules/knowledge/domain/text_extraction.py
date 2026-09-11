from typing import Protocol

from app.modules.knowledge.domain.exceptions import UnsupportedDocumentFormatError


class DocumentTextExtractor(Protocol):
    """Boundary between stored bytes and extracted text. The application layer never decodes
    bytes itself - it depends on this Protocol only (mirrors app.ai.providers.base's pattern).
    """

    def extract(self, content: bytes, *, document_id: int) -> str: ...


class PlainTextExtractor:
    """Stage 4's only concrete extractor. `ResearchDocument.format` is an unconstrained
    string with no approved enumeration (Stage 3 report; 04_Logical_Data_Model.md §3.4) - no
    authoritative document defines accepted format values, so this extractor does not branch
    on the declared `format` label. Instead it attempts a strict UTF-8 decode: content that
    decodes cleanly is treated as extractable text (the MVP's own scope limitation already
    restricts documents to "text-based academic documents", 10_MVP_scope.md §3.2); content
    that does not decode (e.g. a binary PDF/DOCX payload) is unsupported for Stage 4's
    mechanical extractor. Binary-format extraction (PDF, DOCX) is explicitly deferred, not
    silently promised.
    """

    def extract(self, content: bytes, *, document_id: int) -> str:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedDocumentFormatError(document_id=document_id) from exc
