import io

import docx
import pytest

from app.modules.knowledge.domain.exceptions import UnsupportedDocumentFormatError
from app.modules.knowledge.domain.text_extraction import PlainTextExtractor


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _build_pdf_bytes(text: str) -> bytes:
    """A minimal, hand-built single-page PDF with one real text-drawing operator - real PDF
    files are far more complex (compressed streams, embedded fonts) but this exercises the
    same `pypdf` extraction path against a genuinely valid, spec-conformant PDF structure.
    """
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj",
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj",
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>endobj",
        b"4 0 obj<</Length " + str(len(content)).encode() + b">>stream\n" + content + b"\nendstream endobj",
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj + b"\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return pdf


def test_extracts_valid_utf8_text():
    extractor = PlainTextExtractor()
    result = extractor.extract("Hello, research world.".encode("utf-8"), document_id=1)
    assert result == "Hello, research world."


def test_extracts_utf8_text_with_non_ascii_characters():
    extractor = PlainTextExtractor()
    text = "Résumé of the study — café methodology (naïve approach)."
    result = extractor.extract(text.encode("utf-8"), document_id=1)
    assert result == text


def test_empty_bytes_extract_to_empty_string():
    extractor = PlainTextExtractor()
    assert extractor.extract(b"", document_id=1) == ""


def test_malformed_non_utf8_bytes_raise_unsupported_format_error():
    extractor = PlainTextExtractor()
    invalid_utf8 = b"\xff\xfe\x00\x01binary garbage"
    with pytest.raises(UnsupportedDocumentFormatError):
        extractor.extract(invalid_utf8, document_id=1)


def test_binary_pdf_like_header_raises_unsupported_format_error():
    """A real PDF starts with a %PDF- header followed by binary data - not valid UTF-8.
    Confirms Stage 4's extractor correctly rejects binary formats without pretending to
    support them, per its own documented scope.
    """
    extractor = PlainTextExtractor()
    pdf_like_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n\x00\x01\x02\xfe\xff"
    with pytest.raises(UnsupportedDocumentFormatError):
        extractor.extract(pdf_like_bytes, document_id=1)


def test_unsupported_format_error_identifies_the_document():
    extractor = PlainTextExtractor()
    with pytest.raises(UnsupportedDocumentFormatError) as exc_info:
        extractor.extract(b"\xff\xfe", document_id=42)
    assert exc_info.value.document_id == 42


# --- Real .docx support (found necessary: every real document a user tried to upload was a
# .docx file, and none could be processed before this) ---------------------------------------


def test_extracts_text_from_a_real_docx_file():
    content = _build_docx_bytes(["First paragraph of the thesis.", "Second paragraph with more detail."])

    extractor = PlainTextExtractor()
    result = extractor.extract(content, document_id=1)

    assert "First paragraph of the thesis." in result
    assert "Second paragraph with more detail." in result


def test_docx_extraction_preserves_paragraph_order():
    content = _build_docx_bytes(["Alpha.", "Beta.", "Gamma."])

    result = PlainTextExtractor().extract(content, document_id=1)

    assert result.index("Alpha.") < result.index("Beta.") < result.index("Gamma.")


def test_docx_extraction_skips_blank_paragraphs():
    content = _build_docx_bytes(["Real content.", "", "   ", "More real content."])

    result = PlainTextExtractor().extract(content, document_id=1)

    assert result == "Real content.\n\nMore real content."


def test_an_empty_docx_raises_unsupported_format_error():
    content = _build_docx_bytes([])

    with pytest.raises(UnsupportedDocumentFormatError):
        PlainTextExtractor().extract(content, document_id=1)


def test_a_docx_with_only_blank_paragraphs_raises_unsupported_format_error():
    content = _build_docx_bytes(["", "   "])

    with pytest.raises(UnsupportedDocumentFormatError):
        PlainTextExtractor().extract(content, document_id=1)


def test_a_corrupted_zip_that_merely_starts_with_the_docx_magic_bytes_raises_unsupported_format_error():
    """Content-sniffed as a .docx candidate (correct magic bytes) but not actually a valid
    zip/docx package - must fail cleanly, not raise an unhandled exception.
    """
    corrupted = b"PK\x03\x04" + bytes([0xFF, 0xFE, 0x80, 0x81]) * 20

    with pytest.raises(UnsupportedDocumentFormatError):
        PlainTextExtractor().extract(corrupted, document_id=1)


def test_a_docx_that_is_byte_for_byte_valid_utf8_is_still_extracted_as_a_docx():
    """Regression test for a real ordering bug: format magic bytes must be sniffed *before*
    attempting a plain-UTF-8 decode, not only after it fails - a small/simple .docx or PDF can
    occasionally be byte-for-byte valid UTF-8, and decoding it as "plain text" first would
    silently return raw file-format markup as the "extracted" content instead of the real text
    (found via the PDF fixture below, which is entirely ASCII).
    """
    content = _build_docx_bytes(["Real paragraph text, not raw XML markup."])

    result = PlainTextExtractor().extract(content, document_id=1)

    assert result == "Real paragraph text, not raw XML markup."


# --- Real PDF support ------------------------------------------------------------------------


def test_extracts_text_from_a_real_pdf_file():
    content = _build_pdf_bytes("Hello real PDF extraction test.")

    result = PlainTextExtractor().extract(content, document_id=1)

    assert result == "Hello real PDF extraction test."


def test_a_pdf_that_is_byte_for_byte_valid_utf8_is_still_extracted_as_a_pdf_not_raw_markup():
    """The exact regression this fixture originally exposed: a minimal PDF is plain ASCII
    (hence valid UTF-8) end to end, so a naive "try UTF-8 first" extractor would return the raw
    PDF source - `%PDF-1.4\\n1 0 obj<<...` - as if it were the document's real text.
    """
    content = _build_pdf_bytes("Genuinely extracted PDF text.")

    result = PlainTextExtractor().extract(content, document_id=1)

    assert result == "Genuinely extracted PDF text."
    assert "obj" not in result
    assert "%PDF" not in result


def test_a_pdf_with_no_extractable_text_raises_unsupported_format_error():
    """A scanned/image-only PDF has no embedded text layer - unsupported (would need OCR, a
    materially different capability, not attempted here).
    """
    content = _build_pdf_bytes("")

    with pytest.raises(UnsupportedDocumentFormatError):
        PlainTextExtractor().extract(content, document_id=1)


def test_a_corrupted_file_that_merely_starts_with_the_pdf_magic_bytes_raises_unsupported_format_error():
    corrupted = b"%PDF-" + bytes([0xFF, 0xFE, 0x80, 0x81]) * 20

    with pytest.raises(UnsupportedDocumentFormatError):
        PlainTextExtractor().extract(corrupted, document_id=1)
