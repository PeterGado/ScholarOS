from sqlalchemy.orm import Session

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
from app.modules.writing.domain.enums import MemoryRecordStatus, ReviewStatus, WritingProfileStatus
from app.modules.writing.domain.repositories import (
    DraftEvidenceLinkRepository,
    DraftRepository,
    DraftVersionRepository,
    MemoryProvenanceLinkRepository,
    MemoryRecordRepository,
    ProfileCharacteristicRepository,
    ProfileCharacteristicSourceRepository,
    ReviewDecisionRepository,
    ReviewRepository,
    WritingProfileRepository,
)
from app.modules.writing.infrastructure.models import Draft as DraftModel
from app.modules.writing.infrastructure.models import DraftEvidenceLink as DraftEvidenceLinkModel
from app.modules.writing.infrastructure.models import DraftVersion as DraftVersionModel
from app.modules.writing.infrastructure.models import MemoryProvenanceLink as MemoryProvenanceLinkModel
from app.modules.writing.infrastructure.models import MemoryRecord as MemoryRecordModel
from app.modules.writing.infrastructure.models import ProfileCharacteristic as ProfileCharacteristicModel
from app.modules.writing.infrastructure.models import ProfileCharacteristicSource as ProfileCharacteristicSourceModel
from app.modules.writing.infrastructure.models import Review as ReviewModel
from app.modules.writing.infrastructure.models import ReviewDecision as ReviewDecisionModel
from app.modules.writing.infrastructure.models import WritingProfile as WritingProfileModel


class SqlAlchemyDraftRepository(DraftRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, draft: Draft) -> Draft:
        row = DraftModel(agent_id=draft.agent_id, title=draft.title, target=draft.target, status=draft.status)
        self._session.add(row)
        self._session.flush()
        draft.draft_id = row.draft_id
        draft.created_at = row.created_at
        return draft

    def get_by_id(self, draft_id: int) -> Draft | None:
        row = self._session.get(DraftModel, draft_id)
        return self._to_domain(row) if row is not None else None

    def list_by_agent_id(self, agent_id: int) -> list[Draft]:
        rows = self._session.query(DraftModel).filter_by(agent_id=agent_id).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: DraftModel) -> Draft:
        return Draft(
            draft_id=row.draft_id,
            agent_id=row.agent_id,
            title=row.title,
            target=row.target,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=row.deleted_at,
        )


class SqlAlchemyDraftVersionRepository(DraftVersionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, version: DraftVersion) -> DraftVersion:
        row = DraftVersionModel(
            draft_id=version.draft_id,
            version_number=version.version_number,
            content=version.content,
            created_by=version.created_by,
        )
        self._session.add(row)
        self._session.flush()
        version.version_id = row.version_id
        version.created_at = row.created_at
        return version

    def get_by_id(self, version_id: int) -> DraftVersion | None:
        row = self._session.get(DraftVersionModel, version_id)
        return self._to_domain(row) if row is not None else None

    def list_by_draft_id(self, draft_id: int) -> list[DraftVersion]:
        rows = (
            self._session.query(DraftVersionModel)
            .filter_by(draft_id=draft_id)
            .order_by(DraftVersionModel.version_number.asc())
            .all()
        )
        return [self._to_domain(row) for row in rows]

    def get_latest_by_draft_id(self, draft_id: int) -> DraftVersion | None:
        row = (
            self._session.query(DraftVersionModel)
            .filter_by(draft_id=draft_id)
            .order_by(DraftVersionModel.version_number.desc())
            .first()
        )
        return self._to_domain(row) if row is not None else None

    @staticmethod
    def _to_domain(row: DraftVersionModel) -> DraftVersion:
        return DraftVersion(
            version_id=row.version_id,
            draft_id=row.draft_id,
            version_number=row.version_number,
            content=row.content,
            created_at=row.created_at,
            created_by=row.created_by,
        )


class SqlAlchemyReviewRepository(ReviewRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, review: Review) -> Review:
        row = ReviewModel(draft_version_id=review.draft_version_id, status=review.status, notes=review.notes)
        self._session.add(row)
        self._session.flush()
        review.review_id = row.review_id
        review.opened_at = row.opened_at
        return review

    def get_by_id(self, review_id: int) -> Review | None:
        row = self._session.get(ReviewModel, review_id)
        return self._to_domain(row) if row is not None else None

    def get_open_by_draft_version_id(self, draft_version_id: int) -> Review | None:
        row = (
            self._session.query(ReviewModel)
            .filter_by(draft_version_id=draft_version_id, status=ReviewStatus.OPEN)
            .one_or_none()
        )
        return self._to_domain(row) if row is not None else None

    @staticmethod
    def _to_domain(row: ReviewModel) -> Review:
        return Review(
            review_id=row.review_id,
            draft_version_id=row.draft_version_id,
            status=row.status,
            notes=row.notes,
            opened_at=row.opened_at,
            decided_at=row.decided_at,
        )


class SqlAlchemyReviewDecisionRepository(ReviewDecisionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, decision: ReviewDecision) -> ReviewDecision:
        row = ReviewDecisionModel(
            review_id=decision.review_id,
            outcome=decision.outcome,
            rationale=decision.rationale,
            decided_by=decision.decided_by,
        )
        self._session.add(row)
        self._session.flush()
        decision.decision_id = row.decision_id
        decision.decided_at = row.decided_at
        return decision

    def get_by_review_id(self, review_id: int) -> ReviewDecision | None:
        row = self._session.query(ReviewDecisionModel).filter_by(review_id=review_id).one_or_none()
        return self._to_domain(row) if row is not None else None

    @staticmethod
    def _to_domain(row: ReviewDecisionModel) -> ReviewDecision:
        return ReviewDecision(
            decision_id=row.decision_id,
            review_id=row.review_id,
            outcome=row.outcome,
            rationale=row.rationale,
            decided_by=row.decided_by,
            decided_at=row.decided_at,
        )


class SqlAlchemyDraftEvidenceLinkRepository(DraftEvidenceLinkRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, link: DraftEvidenceLink) -> DraftEvidenceLink:
        row = DraftEvidenceLinkModel(
            draft_version_id=link.draft_version_id,
            target_type=link.target_type,
            chunk_id=link.chunk_id,
            document_id=link.document_id,
            created_by=link.created_by,
        )
        self._session.add(row)
        self._session.flush()
        link.link_id = row.link_id
        link.created_at = row.created_at
        return link

    def list_by_draft_version_id(self, draft_version_id: int) -> list[DraftEvidenceLink]:
        rows = self._session.query(DraftEvidenceLinkModel).filter_by(draft_version_id=draft_version_id).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: DraftEvidenceLinkModel) -> DraftEvidenceLink:
        return DraftEvidenceLink(
            link_id=row.link_id,
            draft_version_id=row.draft_version_id,
            target_type=row.target_type,
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            created_at=row.created_at,
            created_by=row.created_by,
        )


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
        rows = self._session.query(ProfileCharacteristicModel).filter_by(profile_id=profile_id).all()
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
        row = ProfileCharacteristicSourceModel(characteristic_id=source.characteristic_id, document_id=source.document_id)
        self._session.add(row)
        self._session.flush()
        source.link_id = row.link_id
        source.created_at = row.created_at
        return source

    def list_by_characteristic_id(self, characteristic_id: int) -> list[ProfileCharacteristicSource]:
        rows = (
            self._session.query(ProfileCharacteristicSourceModel).filter_by(characteristic_id=characteristic_id).all()
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

    def list_current_by_agent_id(self, agent_id: int) -> list[MemoryRecord]:
        rows = (
            self._session.query(MemoryRecordModel)
            .filter_by(agent_id=agent_id, status=MemoryRecordStatus.CURRENT)
            .all()
        )
        return [self._to_domain(row) for row in rows]

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
            review_decision_id=link.review_decision_id,
            conversation_id=link.conversation_id,
            element_id=link.element_id,
            document_id=link.document_id,
            draft_version_id=link.draft_version_id,
        )
        self._session.add(row)
        self._session.flush()
        link.link_id = row.link_id
        link.created_at = row.created_at
        return link

    def list_by_record_id(self, record_id: int) -> list[MemoryProvenanceLink]:
        rows = self._session.query(MemoryProvenanceLinkModel).filter_by(record_id=record_id).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: MemoryProvenanceLinkModel) -> MemoryProvenanceLink:
        return MemoryProvenanceLink(
            link_id=row.link_id,
            record_id=row.record_id,
            source_type=row.source_type,
            review_decision_id=row.review_decision_id,
            conversation_id=row.conversation_id,
            element_id=row.element_id,
            document_id=row.document_id,
            draft_version_id=row.draft_version_id,
            created_at=row.created_at,
        )
