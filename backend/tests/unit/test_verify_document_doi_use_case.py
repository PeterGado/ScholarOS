import pytest

from app.ai.crossref import CrossrefWork
from app.modules.document.application.use_cases import VerifyDocumentDoiUseCase
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.enums import DoiVerificationStatus
from app.modules.document.domain.repositories import DocumentRepository


class FakeDocumentRepository(DocumentRepository):
    def __init__(self, document: ResearchDocument | None = None):
        self._by_id = {1: document} if document is not None else {}

    def get_by_id(self, document_id):
        return self._by_id.get(document_id)

    def get_by_ids(self, document_ids):
        raise NotImplementedError

    def list_by_project_id(self, project_id, *, purpose=None, limit=None, offset=0):
        raise NotImplementedError

    def add(self, document):
        raise NotImplementedError

    def update_processing_status(self, document_id, status, *, processed_at=None):
        raise NotImplementedError

    def update_doi_verification(self, document_id, *, status, author, publication_year):
        document = self._by_id[document_id]
        document.doi_verification_status = status
        document.author = author
        document.publication_year = publication_year

    def mark_deleted(self, document_id, *, deleted_at):
        raise NotImplementedError


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _document(**overrides) -> ResearchDocument:
    defaults = {
        "document_id": 1,
        "project_id": 1,
        "title": "Doc",
        "format": "txt",
        "content_reference": "ref-1",
    }
    defaults.update(overrides)
    return ResearchDocument(**defaults)


def test_a_document_with_no_doi_is_a_no_op():
    document = _document(doi=None)
    documents = FakeDocumentRepository(document)
    uow = FakeUnitOfWork()

    def lookup(doi):
        raise AssertionError("should never be called when the document has no doi")

    VerifyDocumentDoiUseCase(documents, uow, doi_lookup_provider=lookup).execute(document_id=1)

    assert document.doi_verification_status is None
    assert uow.committed is False


def test_a_matching_doi_and_fully_supplied_metadata_is_verified():
    document = _document(doi="10.1038/nphys1170", author="Aspelmeyer, M.", publication_year=2009)
    documents = FakeDocumentRepository(document)
    uow = FakeUnitOfWork()
    work = CrossrefWork(title="Measured measurement", authors=("Aspelmeyer",), year=2009)

    VerifyDocumentDoiUseCase(documents, uow, doi_lookup_provider=lambda doi: work).execute(document_id=1)

    assert document.doi_verification_status == DoiVerificationStatus.VERIFIED
    assert document.author == "Aspelmeyer, M."  # the user's own text is kept, not overwritten
    assert document.publication_year == 2009
    assert uow.committed is True


def test_blank_author_and_year_are_filled_from_a_verified_doi():
    document = _document(doi="10.1038/nphys1170", author=None, publication_year=None)
    documents = FakeDocumentRepository(document)
    uow = FakeUnitOfWork()
    work = CrossrefWork(title="Measured measurement", authors=("Aspelmeyer", "Zeilinger"), year=2009)

    VerifyDocumentDoiUseCase(documents, uow, doi_lookup_provider=lambda doi: work).execute(document_id=1)

    assert document.doi_verification_status == DoiVerificationStatus.VERIFIED
    assert document.author == "Aspelmeyer, Zeilinger"
    assert document.publication_year == 2009


def test_a_mismatched_year_is_flagged_without_overwriting_the_users_metadata():
    document = _document(doi="10.1038/nphys1170", author="Aspelmeyer, M.", publication_year=1999)
    documents = FakeDocumentRepository(document)
    uow = FakeUnitOfWork()
    work = CrossrefWork(title="Measured measurement", authors=("Aspelmeyer",), year=2009)

    VerifyDocumentDoiUseCase(documents, uow, doi_lookup_provider=lambda doi: work).execute(document_id=1)

    assert document.doi_verification_status == DoiVerificationStatus.MISMATCH
    assert document.publication_year == 1999  # left exactly as the user entered it


def test_a_completely_different_author_is_flagged_as_a_mismatch():
    document = _document(doi="10.1038/nphys1170", author="Smith, J.", publication_year=None)
    documents = FakeDocumentRepository(document)
    uow = FakeUnitOfWork()
    work = CrossrefWork(title="Measured measurement", authors=("Aspelmeyer",), year=2009)

    VerifyDocumentDoiUseCase(documents, uow, doi_lookup_provider=lambda doi: work).execute(document_id=1)

    assert document.doi_verification_status == DoiVerificationStatus.MISMATCH
    assert document.author == "Smith, J."


def test_an_unresolvable_doi_is_marked_not_found():
    document = _document(doi="10.9999/not-a-real-doi", author="Someone", publication_year=2020)
    documents = FakeDocumentRepository(document)
    uow = FakeUnitOfWork()

    VerifyDocumentDoiUseCase(documents, uow, doi_lookup_provider=lambda doi: None).execute(document_id=1)

    assert document.doi_verification_status == DoiVerificationStatus.NOT_FOUND
    assert document.author == "Someone"  # untouched
    assert document.publication_year == 2020


@pytest.mark.parametrize(
    "entered_author,real_authors,expected_match",
    [
        ("O. Uadiale", ("Uadiale",), True),  # given-name-first order still overlaps on surname
        ("Uadiale, O.", ("Uadiale",), True),
        ("Uadiale and Fagbemi", ("Uadiale", "Fagbemi"), True),
        ("Completely Different", ("Uadiale",), False),
    ],
)
def test_author_matching_is_token_based_not_exact_string_equality(entered_author, real_authors, expected_match):
    document = _document(doi="10.1/x", author=entered_author, publication_year=None)
    documents = FakeDocumentRepository(document)
    uow = FakeUnitOfWork()
    work = CrossrefWork(title="T", authors=real_authors, year=None)

    VerifyDocumentDoiUseCase(documents, uow, doi_lookup_provider=lambda doi: work).execute(document_id=1)

    expected_status = DoiVerificationStatus.VERIFIED if expected_match else DoiVerificationStatus.MISMATCH
    assert document.doi_verification_status == expected_status
