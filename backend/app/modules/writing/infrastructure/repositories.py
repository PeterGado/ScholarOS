from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.writing.domain.entities import (
    Conversation,
    MemoryProvenanceLink,
    MemoryRecord,
    Message,
    MessageContextLink,
    ProfileCharacteristic,
    ProfileCharacteristicSource,
    WritingProfile,
    WritingSegment,
)
from app.modules.writing.domain.enums import (
    ConversationStatus,
    MemoryRecordStatus,
    WritingProfileStatus,
)
from app.modules.writing.domain.exceptions import DuplicateWritingSegmentNameError
from app.modules.writing.domain.repositories import (
    ConversationRepository,
    MemoryProvenanceLinkRepository,
    MemoryRecordRepository,
    MessageContextLinkRepository,
    MessageRepository,
    ProfileCharacteristicRepository,
    ProfileCharacteristicSourceRepository,
    WritingProfileRepository,
    WritingSegmentRepository,
)
from app.modules.writing.infrastructure.models import Conversation as ConversationModel
from app.modules.writing.infrastructure.models import MemoryProvenanceLink as MemoryProvenanceLinkModel
from app.modules.writing.infrastructure.models import MemoryRecord as MemoryRecordModel
from app.modules.writing.infrastructure.models import Message as MessageModel
from app.modules.writing.infrastructure.models import MessageContextLink as MessageContextLinkModel
from app.modules.writing.infrastructure.models import ProfileCharacteristic as ProfileCharacteristicModel
from app.modules.writing.infrastructure.models import ProfileCharacteristicSource as ProfileCharacteristicSourceModel
from app.modules.writing.infrastructure.models import WritingProfile as WritingProfileModel
from app.modules.writing.infrastructure.models import WritingSegment as WritingSegmentModel


class SqlAlchemyWritingProfileRepository(WritingProfileRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, profile: WritingProfile) -> WritingProfile:
        row = WritingProfileModel(
            agent_id=profile.agent_id, user_id=profile.user_id, name=profile.name, status=profile.status
        )
        self._session.add(row)
        self._session.flush()
        profile.profile_id = row.profile_id
        profile.created_at = row.created_at
        return profile

    def get_by_id(self, profile_id: int) -> WritingProfile | None:
        row = self._session.get(WritingProfileModel, profile_id)
        return self._to_domain(row) if row is not None else None

    def get_active_by_agent_id(self, agent_id: int) -> WritingProfile | None:
        row = (
            self._session.query(WritingProfileModel)
            .filter_by(agent_id=agent_id, status=WritingProfileStatus.ACTIVE)
            .one_or_none()
        )
        return self._to_domain(row) if row is not None else None

    def deactivate(self, profile_id: int, *, updated_at) -> None:
        row = self._session.get(WritingProfileModel, profile_id)
        row.status = WritingProfileStatus.INACTIVE
        row.updated_at = updated_at
        self._session.flush()

    @staticmethod
    def _to_domain(row: WritingProfileModel) -> WritingProfile:
        return WritingProfile(
            profile_id=row.profile_id,
            agent_id=row.agent_id,
            user_id=row.user_id,
            name=row.name,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=row.deleted_at,
        )


class SqlAlchemyProfileCharacteristicRepository(ProfileCharacteristicRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, characteristic: ProfileCharacteristic) -> ProfileCharacteristic:
        row = ProfileCharacteristicModel(
            profile_id=characteristic.profile_id,
            characteristic_type=characteristic.characteristic_type,
            signal=characteristic.signal,
            confidence=characteristic.confidence,
        )
        self._session.add(row)
        self._session.flush()
        characteristic.characteristic_id = row.characteristic_id
        characteristic.created_at = row.created_at
        return characteristic

    def list_by_profile_id(self, profile_id: int) -> list[ProfileCharacteristic]:
        rows = self._session.query(ProfileCharacteristicModel).filter_by(
            profile_id=profile_id).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: ProfileCharacteristicModel) -> ProfileCharacteristic:
        return ProfileCharacteristic(
            characteristic_id=row.characteristic_id,
            profile_id=row.profile_id,
            characteristic_type=row.characteristic_type,
            signal=row.signal,
            confidence=row.confidence,
            created_at=row.created_at,
        )


class SqlAlchemyProfileCharacteristicSourceRepository(ProfileCharacteristicSourceRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, source: ProfileCharacteristicSource) -> ProfileCharacteristicSource:
        row = ProfileCharacteristicSourceModel(
            characteristic_id=source.characteristic_id, document_id=source.document_id)
        self._session.add(row)
        self._session.flush()
        source.link_id = row.link_id
        source.created_at = row.created_at
        return source

    def list_by_characteristic_id(self, characteristic_id: int) -> list[ProfileCharacteristicSource]:
        rows = (
            self._session.query(ProfileCharacteristicSourceModel).filter_by(
                characteristic_id=characteristic_id).all()
        )
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: ProfileCharacteristicSourceModel) -> ProfileCharacteristicSource:
        return ProfileCharacteristicSource(
            link_id=row.link_id,
            characteristic_id=row.characteristic_id,
            document_id=row.document_id,
            created_at=row.created_at,
        )


class SqlAlchemyMemoryRecordRepository(MemoryRecordRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: MemoryRecord) -> MemoryRecord:
        row = MemoryRecordModel(
            agent_id=record.agent_id,
            record_type=record.record_type,
            content=record.content,
            rationale=record.rationale,
            status=record.status,
            created_by=record.created_by,
            superseded_record_id=record.superseded_record_id,
            superseded_at=record.superseded_at,
        )
        self._session.add(row)
        self._session.flush()
        record.record_id = row.record_id
        record.created_at = row.created_at
        return record

    def get_by_id(self, record_id: int) -> MemoryRecord | None:
        row = self._session.get(MemoryRecordModel, record_id)
        return self._to_domain(row) if row is not None else None

    def list_current_by_agent_id(
        self, agent_id: int, *, limit: int | None = None, offset: int = 0
    ) -> list[MemoryRecord]:
        """Most-recently-established first (Persistent Brain v3 audit fix) - callers that cap
        this list (`ContextAssemblyInput.max_memories`) get the most recent memories, not
        whatever order SQLite happens to return; `ListMemoryUseCase`'s inspection listing
        benefits from the same, more useful ordering for free.
        """
        query = (
            self._session.query(MemoryRecordModel)
            .filter_by(agent_id=agent_id, status=MemoryRecordStatus.CURRENT)
            .order_by(MemoryRecordModel.created_at.desc(), MemoryRecordModel.record_id.desc())
        )
        if limit is not None:
            query = query.offset(offset).limit(limit + 1)
        return [self._to_domain(row) for row in query.all()]

    def mark_superseded(self, record_id: int, *, superseded_record_id: int, superseded_at) -> None:
        row = self._session.get(MemoryRecordModel, record_id)
        row.status = MemoryRecordStatus.SUPERSEDED
        row.superseded_record_id = superseded_record_id
        row.superseded_at = superseded_at
        self._session.flush()

    @staticmethod
    def _to_domain(row: MemoryRecordModel) -> MemoryRecord:
        return MemoryRecord(
            record_id=row.record_id,
            agent_id=row.agent_id,
            record_type=row.record_type,
            content=row.content,
            rationale=row.rationale,
            status=row.status,
            created_at=row.created_at,
            created_by=row.created_by,
            superseded_record_id=row.superseded_record_id,
            superseded_at=row.superseded_at,
        )


class SqlAlchemyMemoryProvenanceLinkRepository(MemoryProvenanceLinkRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, link: MemoryProvenanceLink) -> MemoryProvenanceLink:
        row = MemoryProvenanceLinkModel(
            record_id=link.record_id,
            source_type=link.source_type,
            conversation_id=link.conversation_id,
            element_id=link.element_id,
            document_id=link.document_id,
        )
        self._session.add(row)
        self._session.flush()
        link.link_id = row.link_id
        link.created_at = row.created_at
        return link

    def list_by_record_id(self, record_id: int) -> list[MemoryProvenanceLink]:
        rows = self._session.query(MemoryProvenanceLinkModel).filter_by(
            record_id=record_id).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: MemoryProvenanceLinkModel) -> MemoryProvenanceLink:
        return MemoryProvenanceLink(
            link_id=row.link_id,
            record_id=row.record_id,
            source_type=row.source_type,
            conversation_id=row.conversation_id,
            element_id=row.element_id,
            document_id=row.document_id,
            created_at=row.created_at,
        )


class SqlAlchemyConversationRepository(ConversationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, conversation: Conversation) -> Conversation:
        row = ConversationModel(
            agent_id=conversation.agent_id, title=conversation.title, status=conversation.status
        )
        self._session.add(row)
        self._session.flush()
        conversation.conversation_id = row.conversation_id
        conversation.started_at = row.started_at
        return conversation

    def get_by_id(self, conversation_id: int) -> Conversation | None:
        row = self._session.get(ConversationModel, conversation_id)
        return self._to_domain(row) if row is not None else None

    def lock_for_message_sequence(self, conversation_id: int) -> None:
        self._session.query(ConversationModel).filter_by(
            conversation_id=conversation_id).with_for_update().one()

    def list_by_agent_id(
        self, agent_id: int, *, limit: int | None = None, offset: int = 0
    ) -> list[Conversation]:
        # 2026-09-23: added a tie-break (conversation_id) alongside started_at - two
        # Conversations created within the same timestamp resolution would otherwise paginate
        # unstably (a row could appear on two pages or neither, depending on incidental order).
        query = (
            self._session.query(ConversationModel)
            .filter_by(agent_id=agent_id, deleted_at=None)
            .order_by(ConversationModel.started_at.asc(), ConversationModel.conversation_id.asc())
        )
        if limit is not None:
            query = query.offset(offset).limit(limit + 1)
        return [self._to_domain(row) for row in query.all()]

    def mark_summarized(self, conversation_id: int, *, summarized_at) -> None:
        row = self._session.get(ConversationModel, conversation_id)
        row.status = ConversationStatus.SUMMARIZED
        row.summarized_at = summarized_at
        self._session.flush()

    def mark_deleted(self, conversation_id: int, *, deleted_at) -> None:
        row = self._session.get(ConversationModel, conversation_id)
        row.deleted_at = deleted_at
        self._session.flush()

    @staticmethod
    def _to_domain(row: ConversationModel) -> Conversation:
        return Conversation(
            conversation_id=row.conversation_id,
            agent_id=row.agent_id,
            title=row.title,
            status=row.status,
            started_at=row.started_at,
            summarized_at=row.summarized_at,
            deleted_at=row.deleted_at,
        )


class SqlAlchemyMessageRepository(MessageRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, message: Message) -> Message:
        row = MessageModel(
            conversation_id=message.conversation_id,
            sequence=message.sequence,
            direction=message.direction,
            content=message.content,
            origin=message.origin,
        )
        self._session.add(row)
        self._session.flush()
        message.message_id = row.message_id
        message.created_at = row.created_at
        return message

    def get_by_id(self, message_id: int) -> Message | None:
        row = self._session.get(MessageModel, message_id)
        return self._to_domain(row) if row is not None else None

    def count_by_conversation_id(self, conversation_id: int) -> int:
        return self._session.query(MessageModel).filter_by(conversation_id=conversation_id).count()

    def list_by_conversation_id(
        self, conversation_id: int, *, limit: int | None = None, offset: int = 0
    ) -> list[Message]:
        query = self._session.query(MessageModel).filter_by(conversation_id=conversation_id)
        if limit is None:
            query = query.order_by(MessageModel.sequence.asc())
            return [self._to_domain(row) for row in query.all()]
        # Paginated: fetch from the most-recent end (offset 0 = the tail of the conversation),
        # not the beginning, so a chat UI's initial load shows recent messages instead of
        # message #1 of a long conversation. Rows come back most-recent-first; the use case
        # trims the peek row and reverses to chronological order before display.
        query = query.order_by(MessageModel.sequence.desc()).offset(offset).limit(limit + 1)
        return [self._to_domain(row) for row in query.all()]

    @staticmethod
    def _to_domain(row: MessageModel) -> Message:
        return Message(
            message_id=row.message_id,
            conversation_id=row.conversation_id,
            sequence=row.sequence,
            direction=row.direction,
            content=row.content,
            origin=row.origin,
            created_at=row.created_at,
        )


class SqlAlchemyMessageContextLinkRepository(MessageContextLinkRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, link: MessageContextLink) -> MessageContextLink:
        row = MessageContextLinkModel(
            message_id=link.message_id,
            target_type=link.target_type,
            document_id=link.document_id,
            element_id=link.element_id,
            chunk_id=link.chunk_id,
            memory_record_id=link.memory_record_id,
        )
        self._session.add(row)
        self._session.flush()
        link.link_id = row.link_id
        link.created_at = row.created_at
        return link

    def list_by_message_id(self, message_id: int) -> list[MessageContextLink]:
        rows = self._session.query(MessageContextLinkModel).filter_by(
            message_id=message_id).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: MessageContextLinkModel) -> MessageContextLink:
        return MessageContextLink(
            link_id=row.link_id,
            message_id=row.message_id,
            target_type=row.target_type,
            document_id=row.document_id,
            element_id=row.element_id,
            chunk_id=row.chunk_id,
            memory_record_id=row.memory_record_id,
            created_at=row.created_at,
        )


class SqlAlchemyWritingSegmentRepository(WritingSegmentRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, segment: WritingSegment) -> WritingSegment:
        row = WritingSegmentModel(agent_id=segment.agent_id, name=segment.name, instructions=segment.instructions)
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError:
            # A real race, not just a defensive precaution: the application layer's own
            # duplicate-name precheck and this insert are two separate statements. Translated
            # here, at the infrastructure boundary, rather than in the use case - the writing
            # module's application layer is architecturally forbidden from importing sqlalchemy
            # directly (test_writing_dependency_direction.py), so this is the one place that
            # can actually see the real IntegrityError and turn it into a domain exception.
            raise DuplicateWritingSegmentNameError(name=segment.name) from None
        segment.segment_id = row.segment_id
        segment.created_at = row.created_at
        return segment

    def get_by_id(self, segment_id: int) -> WritingSegment | None:
        row = self._session.get(WritingSegmentModel, segment_id)
        return self._to_domain(row) if row is not None else None

    def get_by_agent_id_and_name(self, agent_id: int, name: str) -> WritingSegment | None:
        row = self._session.query(WritingSegmentModel).filter_by(agent_id=agent_id, name=name).one_or_none()
        return self._to_domain(row) if row is not None else None

    def list_by_agent_id(self, agent_id: int) -> list[WritingSegment]:
        rows = (
            self._session.query(WritingSegmentModel)
            .filter_by(agent_id=agent_id)
            .order_by(WritingSegmentModel.name.asc())
            .all()
        )
        return [self._to_domain(row) for row in rows]

    def count_by_agent_id(self, agent_id: int) -> int:
        return self._session.query(WritingSegmentModel).filter_by(agent_id=agent_id).count()

    def update(self, segment_id: int, *, name: str, instructions: str, updated_at: datetime) -> None:
        row = self._session.get(WritingSegmentModel, segment_id)
        row.name = name
        row.instructions = instructions
        row.updated_at = updated_at
        try:
            self._session.flush()
        except IntegrityError:
            # Same race as add() above - a concurrent rename to the same name.
            raise DuplicateWritingSegmentNameError(name=name) from None

    def delete(self, segment_id: int) -> None:
        row = self._session.get(WritingSegmentModel, segment_id)
        self._session.delete(row)
        self._session.flush()

    @staticmethod
    def _to_domain(row: WritingSegmentModel) -> WritingSegment:
        return WritingSegment(
            segment_id=row.segment_id,
            agent_id=row.agent_id,
            name=row.name,
            instructions=row.instructions,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
