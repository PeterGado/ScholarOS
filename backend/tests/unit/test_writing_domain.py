import pytest

from app.modules.writing.domain.entities import (
    Draft,
    DraftEvidenceLink,
    DraftVersion,
    MemoryProvenanceLink,
    MemoryRecord,
    ProfileCharacteristic,
    Review,
    ReviewDecision,
    WritingProfile,
)
from app.modules.writing.domain.enums import (
    DraftEvidenceTargetType,
    DraftStatus,
    MemoryProvenanceSourceType,
    MemoryRecordType,
    ProfileCharacteristicType,
    ReviewOutcome,
    ReviewStatus,
)
from app.modules.writing.domain.exceptions import (
    DraftEvidenceLinkTargetError,
    InvalidDraftTitleError,
    InvalidDraftVersionContentError,
    InvalidDraftVersionNumberError,
    InvalidMemoryRecordContentError,
    InvalidProfileCharacteristicSignalError,
    InvalidWritingProfileNameError,
    MemoryProvenanceLinkTargetError,
)


# --- Draft -------------------------------------------------------------------


def test_draft_create_defaults_to_drafting_status():
    draft = Draft.create(agent_id=1, title="Chapter 1 Draft")
    assert draft.status == DraftStatus.DRAFTING
    assert draft.draft_id is None
    assert draft.deleted_at is None


def test_draft_rejects_blank_title():
    with pytest.raises(InvalidDraftTitleError):
        Draft.create(agent_id=1, title="   ")


def test_draft_has_no_current_version_pointer_attribute():
    """04_Logical_Data_Model.md §6: current version is derived (latest version_number),
    never a stored attribute.
    """
    draft = Draft.create(agent_id=1, title="Thesis")
    assert not hasattr(draft, "current_version_id")


# --- Draft Version -------------------------------------------------------------------


def test_draft_version_rejects_blank_content():
    with pytest.raises(InvalidDraftVersionContentError):
        DraftVersion(draft_id=1, version_number=1, content="")


def test_draft_version_rejects_non_positive_version_number():
    with pytest.raises(InvalidDraftVersionNumberError):
        DraftVersion(draft_id=1, version_number=0, content="Some content")


def test_draft_version_exposes_no_mutation_method():
    """Immutability is enforced by absence of a setter, matching the existing convention for
    Knowledge Element / Chunk Evidence Link (05_Constraints_and_Integrity.md invariant 4).
    """
    version = DraftVersion(draft_id=1, version_number=1, content="Some content")
    public_methods = [name for name in dir(version) if not name.startswith("_") and callable(getattr(version, name))]
    assert public_methods == []


# --- Review / Review Decision -------------------------------------------------------------------


def test_review_defaults_to_open_status():
    review = Review(draft_version_id=1)
    assert review.status == ReviewStatus.OPEN
    assert review.decided_at is None


def test_review_decision_carries_outcome_and_actor():
    decision = ReviewDecision(review_id=1, outcome=ReviewOutcome.APPROVED, decided_by=42)
    assert decision.outcome == ReviewOutcome.APPROVED
    assert decision.decided_by == 42


# --- Draft Evidence Link (exclusive arc) -------------------------------------------------------------------


def test_draft_evidence_link_for_knowledge_chunk_factory():
    link = DraftEvidenceLink.for_knowledge_chunk(draft_version_id=1, chunk_id=7)
    assert link.target_type == DraftEvidenceTargetType.KNOWLEDGE_CHUNK
    assert link.chunk_id == 7
    assert link.document_id is None


def test_draft_evidence_link_for_research_document_factory():
    link = DraftEvidenceLink.for_research_document(draft_version_id=1, document_id=9)
    assert link.target_type == DraftEvidenceTargetType.RESEARCH_DOCUMENT
    assert link.document_id == 9
    assert link.chunk_id is None


def test_draft_evidence_link_rejects_neither_target_set():
    with pytest.raises(DraftEvidenceLinkTargetError):
        DraftEvidenceLink(draft_version_id=1, target_type=DraftEvidenceTargetType.KNOWLEDGE_CHUNK)


def test_draft_evidence_link_rejects_both_targets_set():
    with pytest.raises(DraftEvidenceLinkTargetError):
        DraftEvidenceLink(
            draft_version_id=1, target_type=DraftEvidenceTargetType.KNOWLEDGE_CHUNK, chunk_id=1, document_id=2
        )


def test_draft_evidence_link_rejects_target_type_mismatch():
    with pytest.raises(DraftEvidenceLinkTargetError):
        DraftEvidenceLink(draft_version_id=1, target_type=DraftEvidenceTargetType.KNOWLEDGE_CHUNK, document_id=2)


# --- Writing Profile / Profile Characteristic -------------------------------------------------------------------


def test_writing_profile_rejects_blank_name():
    with pytest.raises(InvalidWritingProfileNameError):
        WritingProfile(agent_id=1, user_id=1, name="")


def test_profile_characteristic_rejects_blank_signal():
    with pytest.raises(InvalidProfileCharacteristicSignalError):
        ProfileCharacteristic(profile_id=1, characteristic_type=ProfileCharacteristicType.STRUCTURE, signal="")


# --- Memory Record / Memory Provenance Link -------------------------------------------------------------------


def test_memory_record_rejects_blank_content():
    with pytest.raises(InvalidMemoryRecordContentError):
        MemoryRecord(agent_id=1, record_type=MemoryRecordType.DECISION, content="")


def test_memory_provenance_link_user_input_requires_zero_targets():
    link = MemoryProvenanceLink(record_id=1, source_type=MemoryProvenanceSourceType.USER_INPUT)
    assert link.review_decision_id is None
    assert link.document_id is None


def test_memory_provenance_link_user_input_rejects_a_target_reference():
    with pytest.raises(MemoryProvenanceLinkTargetError):
        MemoryProvenanceLink(record_id=1, source_type=MemoryProvenanceSourceType.USER_INPUT, document_id=3)


def test_memory_provenance_link_document_source_requires_document_id():
    with pytest.raises(MemoryProvenanceLinkTargetError):
        MemoryProvenanceLink(record_id=1, source_type=MemoryProvenanceSourceType.DOCUMENT)


def test_memory_provenance_link_document_source_rejects_mismatched_reference():
    with pytest.raises(MemoryProvenanceLinkTargetError):
        MemoryProvenanceLink(record_id=1, source_type=MemoryProvenanceSourceType.DOCUMENT, element_id=5)


def test_memory_provenance_link_valid_document_reference():
    link = MemoryProvenanceLink(record_id=1, source_type=MemoryProvenanceSourceType.DOCUMENT, document_id=5)
    assert link.document_id == 5
