from abc import ABC, abstractmethod

from app.modules.writing.domain.entities import (
    Conversation,
    Draft,
    DraftEvidenceLink,
    DraftVersion,
    MemoryProvenanceLink,
    MemoryRecord,
    Message,
    MessageContextLink,
    ProfileCharacteristic,
    ProfileCharacteristicSource,
    Review,
    ReviewDecision,
    WritingProfile,
)
from app.modules.writing.domain.enums import DraftStatus


class DraftRepository(ABC):
    @abstractmethod
    def add(self, draft: Draft) -> Draft: ...

    @abstractmethod
    def get_by_id(self, draft_id: int) -> Draft | None: ...

    @abstractmethod
    def list_by_agent_id(self, agent_id: int) -> list[Draft]: ...

    @abstractmethod
    def update_status(self, draft_id: int, status: DraftStatus) -> None:
        """Added Stage 7: the review-submission use case is the first caller that needs to
        transition Draft.status (05_Constraints_and_Integrity.md lifecycle table:
        in_review -> approved; in_review -> drafting on revisions_requested).
        """
        ...


class DraftVersionRepository(ABC):
    @abstractmethod
    def add(self, version: DraftVersion) -> DraftVersion: ...

    @abstractmethod
    def get_by_id(self, version_id: int) -> DraftVersion | None: ...

    @abstractmethod
    def list_by_draft_id(self, draft_id: int) -> list[DraftVersion]:
        """Ordered by version_number ascending - the last element is the current version
        (04_Logical_Data_Model.md §6: "current" is derived, never stored).
        """
        ...

    @abstractmethod
    def get_latest_by_draft_id(self, draft_id: int) -> DraftVersion | None: ...


class ReviewRepository(ABC):
    @abstractmethod
    def add(self, review: Review) -> Review: ...

    @abstractmethod
    def get_by_id(self, review_id: int) -> Review | None: ...

    @abstractmethod
    def get_open_by_draft_version_id(self, draft_version_id: int) -> Review | None: ...


class ReviewDecisionRepository(ABC):
    @abstractmethod
    def add(self, decision: ReviewDecision) -> ReviewDecision: ...

    @abstractmethod
    def get_by_review_id(self, review_id: int) -> ReviewDecision | None: ...


class DraftEvidenceLinkRepository(ABC):
    @abstractmethod
    def add(self, link: DraftEvidenceLink) -> DraftEvidenceLink: ...

    @abstractmethod
    def list_by_draft_version_id(self, draft_version_id: int) -> list[DraftEvidenceLink]: ...


class WritingProfileRepository(ABC):
    @abstractmethod
    def add(self, profile: WritingProfile) -> WritingProfile: ...

    @abstractmethod
    def get_by_id(self, profile_id: int) -> WritingProfile | None: ...

    @abstractmethod
    def get_active_by_agent_id(self, agent_id: int) -> WritingProfile | None: ...


class ProfileCharacteristicRepository(ABC):
    @abstractmethod
    def add(self, characteristic: ProfileCharacteristic) -> ProfileCharacteristic: ...

    @abstractmethod
    def list_by_profile_id(self, profile_id: int) -> list[ProfileCharacteristic]: ...


class ProfileCharacteristicSourceRepository(ABC):
    @abstractmethod
    def add(self, source: ProfileCharacteristicSource) -> ProfileCharacteristicSource: ...

    @abstractmethod
    def list_by_characteristic_id(self, characteristic_id: int) -> list[ProfileCharacteristicSource]: ...


class MemoryRecordRepository(ABC):
    @abstractmethod
    def add(self, record: MemoryRecord) -> MemoryRecord: ...

    @abstractmethod
    def get_by_id(self, record_id: int) -> MemoryRecord | None: ...

    @abstractmethod
    def list_current_by_agent_id(self, agent_id: int) -> list[MemoryRecord]: ...


class MemoryProvenanceLinkRepository(ABC):
    @abstractmethod
    def add(self, link: MemoryProvenanceLink) -> MemoryProvenanceLink: ...

    @abstractmethod
    def list_by_record_id(self, record_id: int) -> list[MemoryProvenanceLink]: ...


class ConversationRepository(ABC):
    @abstractmethod
    def add(self, conversation: Conversation) -> Conversation: ...

    @abstractmethod
    def get_by_id(self, conversation_id: int) -> Conversation | None: ...

    @abstractmethod
    def get_by_agent_id_and_title(self, agent_id: int, title: str) -> Conversation | None:
        """The find-or-create lookup `RequestDraftGenerationUseCase` uses to resolve "the
        Conversation for Draft N" without a `draft_id` column on the frozen Conversation shape.
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


class MessageContextLinkRepository(ABC):
    @abstractmethod
    def add(self, link: MessageContextLink) -> MessageContextLink: ...

    @abstractmethod
    def list_by_message_id(self, message_id: int) -> list[MessageContextLink]: ...
