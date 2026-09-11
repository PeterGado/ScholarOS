import pytest

from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.exceptions import ResearchDocumentNotFoundError
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.knowledge.application.use_cases import ProcessDocumentUseCase
from app.modules.knowledge.domain.exceptions import EmptyExtractedTextError, MissingStoredContentError, UnsupportedDocumentFormatError
from app.modules.knowledge.domain.text_extraction import PlainTextExtractor


class FakeDocumentRepository(DocumentRepository):
    def __init__(self, documents: dict[int, ResearchDocument] | None = None):
        self._documents = documents or {}

    def get_by_id(self, document_id):
        return self._documents.get(document_id)

    def list_by_project_id(self, project_id):
        raise NotImplementedError

    def add(self, document):
        raise NotImplementedError

    def update_processing_status(self, document_id, status, *, processed_at=None):
        raise NotImplementedError


class FakeContentStore:
    def __init__(self, files: dict[str, bytes] | None = None):
        self._files = files or {}
        self.read_calls: list[str] = []

    def save(self, content, *, extension=""):
        raise NotImplementedError

    def read(self, reference: str) -> bytes:
        self.read_calls.append(reference)
        return self._files[reference]

    def exists(self, reference: str) -> bool:
        return reference in self._files


def _document(document_id=1, content_reference="ref-1", format="txt") -> ResearchDocument:
    return ResearchDocument(
        document_id=document_id,
        project_id=1,
        title="A Document",
        format=format,
        content_reference=content_reference,
    )


def test_processes_a_valid_document_into_chunks():
    document = _document()
    documents = FakeDocumentRepository({1: document})
    content_store = FakeContentStore({"ref-1": b"Paragraph one.\n\nParagraph two."})
    use_case = ProcessDocumentUseCase(documents, content_store, PlainTextExtractor())

    chunks = use_case.execute(document_id=1)

    assert len(chunks) == 1
    assert chunks[0].text == "Paragraph one.\n\nParagraph two."
    assert chunks[0].document_id == 1
    assert content_store.read_calls == ["ref-1"]


def test_document_not_found_raises():
    use_case = ProcessDocumentUseCase(FakeDocumentRepository({}), FakeContentStore({}), PlainTextExtractor())
    with pytest.raises(ResearchDocumentNotFoundError):
        use_case.execute(document_id=999)


def test_missing_stored_content_raises():
    """The database row exists but the referenced object does not (Stage 4 failure mode)."""
    document = _document(content_reference="ref-missing")
    documents = FakeDocumentRepository({1: document})
    content_store = FakeContentStore({})  # nothing stored
    use_case = ProcessDocumentUseCase(documents, content_store, PlainTextExtractor())

    with pytest.raises(MissingStoredContentError):
        use_case.execute(document_id=1)


def test_unsupported_binary_content_raises():
    document = _document()
    documents = FakeDocumentRepository({1: document})
    content_store = FakeContentStore({"ref-1": b"\xff\xfe\x00\x01binary"})
    use_case = ProcessDocumentUseCase(documents, content_store, PlainTextExtractor())

    with pytest.raises(UnsupportedDocumentFormatError):
        use_case.execute(document_id=1)


def test_empty_document_content_raises():
    document = _document()
    documents = FakeDocumentRepository({1: document})
    content_store = FakeContentStore({"ref-1": b""})
    use_case = ProcessDocumentUseCase(documents, content_store, PlainTextExtractor())

    with pytest.raises(EmptyExtractedTextError):
        use_case.execute(document_id=1)


def test_whitespace_only_document_content_raises():
    document = _document()
    documents = FakeDocumentRepository({1: document})
    content_store = FakeContentStore({"ref-1": b"   \n\n\t  "})
    use_case = ProcessDocumentUseCase(documents, content_store, PlainTextExtractor())

    with pytest.raises(EmptyExtractedTextError):
        use_case.execute(document_id=1)


def test_reprocessing_the_same_document_is_idempotent_and_produces_no_side_effects():
    """No persistence occurs at all in this use case - the only meaningful notion of
    idempotency here is "identical output, no accumulating side effect" (Stage 4 §16).
    """
    document = _document()
    documents = FakeDocumentRepository({1: document})
    content_store = FakeContentStore({"ref-1": b"Paragraph one.\n\nParagraph two."})
    use_case = ProcessDocumentUseCase(documents, content_store, PlainTextExtractor())

    first = use_case.execute(document_id=1)
    second = use_case.execute(document_id=1)

    assert first == second
    assert content_store.read_calls == ["ref-1", "ref-1"]  # read twice, nothing ever written


def test_processing_does_not_mutate_the_document_or_write_to_the_content_store():
    document = _document()
    documents = FakeDocumentRepository({1: document})
    content_store = FakeContentStore({"ref-1": b"Some content."})
    use_case = ProcessDocumentUseCase(documents, content_store, PlainTextExtractor())

    use_case.execute(document_id=1)

    assert documents.get_by_id(1).processing_status.value == "pending"  # unchanged
