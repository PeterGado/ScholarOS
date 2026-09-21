# Deliberately duplicates the two magic-byte constants text_extraction.py already defines
# (app/modules/knowledge/domain/text_extraction.py) rather than importing them from there: a
# module under app/core must not depend on a specific module's domain layer (the reverse of the
# allowed direction - modules depend on core, not the other way around). Two one-line byte
# constants duplicated is a smaller risk than restructuring already-tested extraction code.
_DOCX_MAGIC = b"PK\x03\x04"
_PDF_MAGIC = b"%PDF-"


def looks_like_a_supported_document(content: bytes) -> bool:
    """Cheap, sniff-only check (magic bytes / UTF-8 decodability) - the same signals
    PlainTextExtractor.extract uses to choose a parser, without doing the actual parse.

    Used at upload time (2026-09-21 security pass: no format allowlist existed anywhere - any
    file type was accepted, stored, and queued for processing, only failing later with
    UnsupportedDocumentFormatError once a Work Item actually tried it) to reject a file that
    could never be processed, immediately, before it consumes any storage or queue capacity.

    Deliberately not a full extraction: content whose bytes merely *look* right but are
    corrupt or empty (a truncated PDF, an empty .docx) is still accepted here and only
    discovered during real processing, exactly as before - this only rejects a file that is
    unambiguously the wrong kind of file altogether, not a real .docx/PDF's internal validity.
    """
    if content.startswith(_DOCX_MAGIC) or content.startswith(_PDF_MAGIC):
        return True
    try:
        content.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False
