from abc import ABC, abstractmethod
from datetime import datetime

from app.modules.writing.domain.entities import (
    Conversation,
    MemoryProvenanceLink,
    MemoryRecord,
    Message,
    MessageContextLink,
    ProfileCharacteristic,
    ProfileCharacteristicSource,
    WritingProfile,
)


class WritingProfileRepository(ABC):
    @abstractmethod
    def add(self, profile: WritingProfile) -> WritingProfile: ...

    @abstractmethod
    def get_by_id(self, profile_id: int) -> WritingProfile | None: ...

    @abstractmethod
    def get_active_by_agent_id(
        self, agent_id: int) -> WritingProfile | None: ...

    @abstractmethod
    def deactivate(self, profile_id: int, *, updated_at: datetime) -> None: ...


class ProfileCharacteristicRepository(ABC):
    @abstractmethod
    def add(self, characteristic: ProfileCharacteristic) -> ProfileCharacteristic: ...

    @abstractmethod
    def list_by_profile_id(
        self, profile_id: int) -> list[ProfileCharacteristic]: ...


class ProfileCharacteristicSourceRepository(ABC):
    @abstractmethod
    def add(
        self, source: ProfileCharacteristicSource) -> ProfileCharacteristicSource: ...

    @abstractmethod
    def list_by_characteristic_id(
        self, characteristic_id: int) -> list[ProfileCharacteristicSource]: ...


class MemoryRecordRepository(ABC):
    @abstractmethod
    def add(self, record: MemoryRecord) -> MemoryRecord: ...

    @abstractmethod
    def get_by_id(self, record_id: int) -> MemoryRecord | None: ...

    @abstractmethod
    def list_current_by_agent_id(
        self, agent_id: int, *, limit: int | None = None, offset: int = 0) -> list[MemoryRecord]:
        """`limit=None` (the default) returns every current Memory Record, unbounded - what
        every existing caller (context assembly's own `max_memories` capping happens
        afterward, in Python) still gets. `limit`/`offset` (2026-09-23, pagination for
        `GET /writing/memory`) are additive - passing `limit` returns up to `limit + 1` rows so
        the caller can detect "more exist" without a second COUNT query.
        """
        ...

    @abstractmethod
    def mark_superseded(self, record_id: int, *, superseded_record_id: int, superseded_at: datetime) -> None:
        """Transitions a Memory Record `current -> superseded` (04_Logical_Data_Model.md §3.8;
        `MemoryRecordStatus.SUPERSEDED`), exercising a write path that has existed in the
        frozen schema with zero callers since Stage 2 (Persistent Brain v2, memory inspection/
        correction). Never deletes the row - superseded records remain readable, just excluded
        from `list_current_by_agent_id`, preserving history.
        """
        ...


class MemoryProvenanceLinkRepository(ABC):
    @abstractmethod
    def add(self, link: MemoryProvenanceLink) -> MemoryProvenanceLink: ...

    @abstractmethod
    def list_by_record_id(
        self, record_id: int) -> list[MemoryProvenanceLink]: ...


class ConversationRepository(ABC):
    @abstractmethod
    def add(self, conversation: Conversation) -> Conversation: ...

    @abstractmethod
    def get_by_id(self, conversation_id: int) -> Conversation | None: ...

    @abstractmethod
    def lock_for_message_sequence(self, conversation_id: int) -> None:
        """Serializes message sequence allocation for this Conversation."""
        ...

    @abstractmethod
    def list_by_agent_id(self, agent_id: int, *, limit: int | None = None, offset: int = 0) -> list[Conversation]:
        """Every standalone Agent Workspace chat conversation owned by an Agent
        (Persistent Brain Decision 3). `limit=None` (the default) is unbounded; `limit`/
        `offset` (2026-09-23, pagination for `GET /writing/conversations`) return up to
        `limit + 1` rows so the caller can detect "more exist" without a second COUNT query.
        """
        ...

    @abstractmethod
    def mark_summarized(self, conversation_id: int, *, summarized_at: datetime) -> None:
        """Records that a rolling summary Message now exists for this Conversation - exercises
        the frozen `status`/`summarized_at` fields (04_Logical_Data_Model.md §3.9;
        `ConversationStatus.SUMMARIZED`) for the first time (Persistent Brain v2, scalable
        conversation memory). The summary's actual text lives in a Message row (see
        `conversation_context.CONVERSATION_SUMMARY_ORIGIN`), not here - this only updates the
        Conversation's own bookkeeping fields.
        """
        ...

    @abstractmethod
    def mark_deleted(self, conversation_id: int, *, deleted_at: datetime) -> None:
        """Soft-deletes a Conversation (exercises the frozen `deleted_at` field for the first
        time). Its Messages are never touched or deleted - only the Conversation itself is
        excluded from `list_by_agent_id` and treated as not-found by every use case that
        resolves one by id, preserving the underlying continuity record.
        """
        ...


class MessageRepository(ABC):
    @abstractmethod
    def add(self, message: Message) -> Message: ...

    @abstractmethod
    def get_by_id(self, message_id: int) -> Message | None: ...

    @abstractmethod
    def count_by_conversation_id(self, conversation_id: int) -> int:
        """Used to compute the next `sequence` value for a new Message."""
        ...

    @abstractmethod
    def list_by_conversation_id(
        self, conversation_id: int, *, limit: int | None = None, offset: int = 0) -> list[Message]:
        """`limit=None` (the default) returns the full history for its Conversation ordered by
        `sequence` ascending, unchanged - used to resolve bounded RELEVANT CONVERSATION CONTEXT
        for generation (Persistent Brain Decision 3), where callers bound to the most recent N
        themselves via `ContextAssemblyInput.max_conversation_messages`.

        `limit`/`offset` (2026-09-23, pagination for `GET /writing/conversations/{id}/messages`)
        fetch from the *most recent* end instead (`offset=0` is the tail of the conversation,
        not the beginning) so a chat UI's initial page shows recent messages rather than the
        start of a long conversation - and return up to `limit + 1` rows, most-recent-first, so
        the caller can detect "more exist" without a second COUNT query. Callers restore
        chronological order themselves after trimming the peek row.
        """
        ...


class MessageContextLinkRepository(ABC):
    @abstractmethod
    def add(self, link: MessageContextLink) -> MessageContextLink: ...

    @abstractmethod
    def list_by_message_id(
        self, message_id: int) -> list[MessageContextLink]: ...
