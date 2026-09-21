from app.core.document_formats import looks_like_a_supported_document


def test_plain_utf8_text_is_supported():
    assert looks_like_a_supported_document("Some real text content.".encode("utf-8")) is True


def test_docx_magic_bytes_are_supported():
    assert looks_like_a_supported_document(b"PK\x03\x04" + b"rest of a real docx zip") is True


def test_pdf_magic_bytes_are_supported():
    assert looks_like_a_supported_document(b"%PDF-1.4\nrest of a real pdf") is True


def test_invalid_utf8_with_no_recognized_magic_bytes_is_not_supported():
    assert looks_like_a_supported_document(b"\xff\xfebinary garbage") is False


def test_empty_content_is_treated_as_valid_utf8_text():
    """An empty file decodes as an empty string - not this check's job to reject an empty
    upload (EmptyDocumentContentError, raised elsewhere, already covers that)."""
    assert looks_like_a_supported_document(b"") is True


def test_corrupt_content_with_real_docx_magic_bytes_still_passes_the_sniff():
    """Deliberately not a full parse - a corrupt .docx is caught later, at real processing
    time (UnsupportedDocumentFormatError), not by this cheap upload-time check."""
    assert looks_like_a_supported_document(b"PK\x03\x04" + b"not actually a valid zip") is True
