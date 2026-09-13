from abc import ABC, abstractmethod

from app.modules.writing.domain.entities import (
    Draft,
    DraftEvidenceLink,
    DraftVersion,
    MemoryProvenanceLink,
    MemoryRecord,
    ProfileCharacteristic,
    ProfileCharacteristicSource,
    Review,
    ReviewDecision,
    WritingProfile,
)


class DraftRepository(ABC):
    @abstractmethod
    def add(self, draft: Draft) -> Draft: ...

    @abstractmethod
    def get_by_id(self, draft_id: int) -> Draft | None: ...

    @abstractmethod
    def list_by_agent_id(self, agent_id: int) -> list[Draft]: ...


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
