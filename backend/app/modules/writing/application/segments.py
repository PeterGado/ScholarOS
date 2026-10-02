from datetime import datetime, timezone

from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.writing.domain.entities import WritingSegment
from app.modules.writing.domain.exceptions import (
    DuplicateWritingSegmentNameError,
    TooManyWritingSegmentsError,
    WritingSegmentNotFoundError,
)
from app.modules.writing.domain.repositories import WritingSegmentRepository

MAX_WRITING_SEGMENTS_PER_AGENT = 50
"""Generous even for a heavily-subdivided thesis (most real projects need far fewer named
segments than this), but still bounded rather than unlimited - matches this codebase's
established pattern of capping every user-created collection (research documents, writing
style samples)."""


def _get_owned_segment(segments: WritingSegmentRepository, *, agent_id: int, segment_id: int) -> WritingSegment:
    """Shared ownership resolution for Update/Delete - deliberately indistinguishable (non-
    enumeration) whether the segment_id doesn't exist at all or belongs to a different Agent,
    mirroring every other ownership check in this module.
    """
    segment = segments.get_by_id(segment_id)
    if segment is None or segment.agent_id != agent_id:
        raise WritingSegmentNotFoundError(segment_id=segment_id)
    return segment


class CreateWritingSegmentUseCase:
    """Creates a named project segment (e.g. "Background of the Study") with its own saved
    writing instructions (2026-10-02) - see WritingSegment's own docstring for why this is
    plain CRUD, not a supersession-tracked record.
    """

    def __init__(
        self,
        segment_repository: WritingSegmentRepository,
        agent_repository: AgentRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._segments = segment_repository
        self._agents = agent_repository
        self._uow = unit_of_work

    def execute(self, *, user_id: int, name: str, instructions: str) -> WritingSegment:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        if self._segments.count_by_agent_id(agent.agent_id) >= MAX_WRITING_SEGMENTS_PER_AGENT:
            raise TooManyWritingSegmentsError(limit=MAX_WRITING_SEGMENTS_PER_AGENT)

        if self._segments.get_by_agent_id_and_name(agent.agent_id, name) is not None:
            raise DuplicateWritingSegmentNameError(name=name)

        try:
            segment = self._segments.add(
                WritingSegment(agent_id=agent.agent_id, name=name, instructions=instructions)
            )
            self._uow.commit()
        except Exception:
            # Covers a real race, not just a defensive precaution: the duplicate-name check
            # above and the repository's own insert are two separate statements - the
            # repository (app.modules.writing.infrastructure.repositories, the one place
            # allowed to see a raw IntegrityError) already translates that race into the same
            # DuplicateWritingSegmentNameError the precheck raises, so there is nothing
            # SQLAlchemy-specific to catch here - just roll back and let it propagate.
            self._uow.rollback()
            raise
        return segment


class ListWritingSegmentsUseCase:
    def __init__(self, segment_repository: WritingSegmentRepository, agent_repository: AgentRepository) -> None:
        self._segments = segment_repository
        self._agents = agent_repository

    def execute(self, *, user_id: int) -> list[WritingSegment]:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)
        return self._segments.list_by_agent_id(agent.agent_id)


class UpdateWritingSegmentUseCase:
    def __init__(
        self,
        segment_repository: WritingSegmentRepository,
        agent_repository: AgentRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._segments = segment_repository
        self._agents = agent_repository
        self._uow = unit_of_work

    def execute(self, *, user_id: int, segment_id: int, name: str, instructions: str) -> WritingSegment:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        segment = _get_owned_segment(self._segments, agent_id=agent.agent_id, segment_id=segment_id)

        existing = self._segments.get_by_agent_id_and_name(agent.agent_id, name)
        if existing is not None and existing.segment_id != segment_id:
            raise DuplicateWritingSegmentNameError(name=name)

        updated_at = datetime.now(timezone.utc)
        try:
            self._segments.update(segment_id, name=name, instructions=instructions, updated_at=updated_at)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        segment.name = name
        segment.instructions = instructions
        segment.updated_at = updated_at
        return segment


class DeleteWritingSegmentUseCase:
    def __init__(
        self,
        segment_repository: WritingSegmentRepository,
        agent_repository: AgentRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._segments = segment_repository
        self._agents = agent_repository
        self._uow = unit_of_work

    def execute(self, *, user_id: int, segment_id: int) -> None:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        _get_owned_segment(self._segments, agent_id=agent.agent_id, segment_id=segment_id)

        try:
            self._segments.delete(segment_id)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
