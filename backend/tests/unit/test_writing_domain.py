import pytest

from app.modules.writing.domain.entities import (
    Conversation,
    MemoryProvenanceLink,
    MemoryRecord,
    Message,
    MessageContextLink,
    ProfileCharacteristic,
    WritingProfile,
)
from app.modules.writing.domain.enums import (
    ConversationStatus,
    MemoryProvenanceSourceType,
    MemoryRecordType,
    MessageContextTargetType,
    MessageDirection,
    ProfileCharacteristicType,
)
from app.modules.writing.domain.exceptions import (
    InvalidMemoryRecordContentError,
    InvalidMessageContentError,
    InvalidMessageSequenceError,
    InvalidProfileCharacteristicSignalError,
    InvalidWritingProfileNameError,
    MemoryProvenanceLinkTargetError,
    MessageContextLinkTargetError,
)


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
    assert link.conversation_id is None
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


def test_memory_provenance_link_valid_conversation_reference():
    link = MemoryProvenanceLink(record_id=1, source_type=MemoryProvenanceSourceType.CONVERSATION, conversation_id=9)
    assert link.conversation_id == 9


# --- Conversation / Message / Message Context Link -------------------------------------------------------------------


def test_conversation_defaults_to_active_status():
    conversation = Conversation(agent_id=1, title="Untitled conversation")
    assert conversation.status == ConversationStatus.ACTIVE


def test_message_rejects_blank_content():
    with pytest.raises(InvalidMessageContentError):
        Message(conversation_id=1, sequence=1, direction=MessageDirection.USER_REQUEST, content=" ")


def test_message_rejects_a_non_positive_sequence():
    with pytest.raises(InvalidMessageSequenceError):
        Message(conversation_id=1, sequence=0, direction=MessageDirection.USER_REQUEST, content="Write the intro.")


def test_message_context_link_requires_exactly_one_target():
    with pytest.raises(MessageContextLinkTargetError):
        MessageContextLink(message_id=1, target_type=MessageContextTargetType.MEMORY_RECORD)


def test_message_context_link_rejects_mismatched_reference():
    with pytest.raises(MessageContextLinkTargetError):
        MessageContextLink(message_id=1, target_type=MessageContextTargetType.MEMORY_RECORD, document_id=5)


def test_message_context_link_valid_memory_record_reference():
    link = MessageContextLink(message_id=1, target_type=MessageContextTargetType.MEMORY_RECORD, memory_record_id=7)
    assert link.memory_record_id == 7
