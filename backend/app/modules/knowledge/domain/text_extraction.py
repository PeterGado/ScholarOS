import io
import zipfile
from typing import Protocol

import docx
import pypdf

from app.modules.knowledge.domain.exceptions import UnsupportedDocumentFormatError

_DOCX_MAGIC = b"PK\x03\x04"
"""A .docx file is a zip archive (of XML parts) - this is the standard zip local-file-header
signature. Sniffed on content, not the client-supplied `format` label (see class docstring
below for why label-sniffing is deliberately avoided throughout this extractor).
"""

_PDF_MAGIC = b"%PDF-"
"""Every PDF file begins with this header, by specification."""


class DocumentTextExtractor(Protocol):
    """Boundary between stored bytes and extracted text. The application layer never decodes
    bytes itself - it depends on this Protocol only (mirrors app.ai.providers.base's pattern).
    """

    def extract(self, content: bytes, *, document_id: int) -> str: ...


class PlainTextExtractor:
    """Stage 4's mechanical extractor, extended to also support Word (.docx) and PDF documents
    (found necessary during real manual use: every real document a user tried to upload was a
    .docx or PDF file, and none could ever be processed before this). `ResearchDocument.format`
    is an unconstrained string with no approved enumeration (Stage 3 report; 04_Logical_Data_
    Model.md §3.4) - no authoritative document defines accepted format values, so this
    extractor still does not branch on the declared `format` label, consistent with its
    original design. Instead it tries, in order: a strict UTF-8 decode (plain text); .docx
    parsing (detected by the zip magic bytes actually present in the content); PDF parsing
    (detected by the PDF header actually present in the content) via `pypdf` - text-based PDFs
    only, a scanned/image-only PDF has no embedded text layer and is not supported (that would
    require OCR, a materially different capability, not attempted here). Anything that
    satisfies none of these is unsupported. Legacy .doc remains explicitly deferred.
    """

    def extract(self, content: bytes, *, document_id: int) -> str:
        # Recognized binary formats are sniffed *before* attempting a plain-UTF-8 decode, not
        # after it fails: a real .docx/PDF is virtually always binary and would fail UTF-8
        # decoding anyway, but a small/simple one can occasionally be byte-for-byte valid
        # UTF-8 (found via a hand-built test PDF) - decoding it as "plain text" then would
        # silently return raw file-format markup as if it were the document's real content,
        # succeeding with garbage instead of failing loudly. Recognizing the format by its
        # actual magic bytes first avoids that regardless of what the content happens to decode
        # as.
        if content.startswith(_DOCX_MAGIC):
            try:
                return _extract_docx_text(content)
            except (zipfile.BadZipFile, KeyError, ValueError, docx.opc.exceptions.PackageNotFoundError):
                raise UnsupportedDocumentFormatError(document_id=document_id) from None

        if content.startswith(_PDF_MAGIC):
            try:
                return _extract_pdf_text(content)
            except (pypdf.errors.PdfReadError, ValueError):
                raise UnsupportedDocumentFormatError(document_id=document_id) from None

        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            raise UnsupportedDocumentFormatError(document_id=document_id) from None


def _extract_docx_text(content: bytes) -> str:
    document = docx.Document(io.BytesIO(content))
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    text = "\n\n".join(paragraphs)
    if not text.strip():
        raise ValueError("The .docx file contained no extractable text")
    return text


def _extract_pdf_text(content: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(page.strip() for page in pages if page.strip())
    if not text.strip():
        raise ValueError("The PDF contained no extractable text (it may be a scanned/image-only PDF)")
    return text
