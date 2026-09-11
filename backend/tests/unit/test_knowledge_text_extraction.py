import pytest

from app.modules.knowledge.domain.exceptions import UnsupportedDocumentFormatError
from app.modules.knowledge.domain.text_extraction import PlainTextExtractor


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
