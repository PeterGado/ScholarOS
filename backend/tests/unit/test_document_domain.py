import pytest

from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.enums import DocumentProcessingStatus
from app.modules.document.domain.exceptions import (
    EmptyDocumentContentError,
    InvalidDocumentFormatError,
    InvalidDocumentTitleError,
)


def test_create_produces_a_pending_document():
    document = ResearchDocument.create(
        project_id=1, title="Source A", format="pdf", content_reference="ref-1"
    )
    assert document.project_id == 1
    assert document.document_id is None
    assert document.processing_status == DocumentProcessingStatus.PENDING


@pytest.mark.parametrize("title", ["", "   ", None])
def test_construction_rejects_missing_title(title):
    with pytest.raises(InvalidDocumentTitleError):
        ResearchDocument(project_id=1, title=title, format="pdf", content_reference="ref-1")


@pytest.mark.parametrize("fmt", ["", "   ", None])
def test_construction_rejects_missing_format(fmt):
    with pytest.raises(InvalidDocumentFormatError):
        ResearchDocument(project_id=1, title="Source A", format=fmt, content_reference="ref-1")


@pytest.mark.parametrize("reference", ["", "   ", None])
def test_construction_rejects_missing_content_reference(reference):
    with pytest.raises(EmptyDocumentContentError):
        ResearchDocument(project_id=1, title="Source A", format="pdf", content_reference=reference)
