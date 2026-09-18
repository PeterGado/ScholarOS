from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.writing.domain.entities import MemoryProvenanceLink, MemoryRecord
from app.modules.writing.domain.enums import CreatedBy, MemoryProvenanceSourceType, MemoryRecordStatus
from app.modules.writing.domain.exceptions import MemoryRecordAlreadySupersededError, MemoryRecordNotFoundError
from app.modules.writing.domain.repositories import MemoryProvenanceLinkRepository, MemoryRecordRepository


@dataclass
class MemoryRecordWithProvenance:
    """A Memory Record bundled with its provenance links - Persistent Brain v2's "let the user
    see what the brain remembers... show provenance" requirement. Mirrors
    `DraftVersionWithEvidence`'s own reasoning: the interface layer never makes a second
    repository call itself.
    """

    record: MemoryRecord
    provenance: list[MemoryProvenanceLink]


class ListMemoryUseCase:
    """Lists the authenticated user's own Agent's current Memory Records with provenance -
    read-only, Agent-scoped, the memory-inspection counterpart of `GetWritingProfileUseCase`.
    An Agent with no memory yet returns an empty list (200), not a 404 - a normal state, not
    an error condition (mirrors `ListDraftsUseCase`'s own precedent).
    """

    def __init__(
        self,
        memory_record_repository: MemoryRecordRepository,
        memory_provenance_link_repository: MemoryProvenanceLinkRepository,
        agent_repository: AgentRepository,
    ) -> None:
        self._memory_records = memory_record_repository
        self._provenance_links = memory_provenance_link_repository
        self._agents = agent_repository

    def execute(self, *, user_id: int) -> list[MemoryRecordWithProvenance]:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        records = self._memory_records.list_current_by_agent_id(agent.agent_id)
        return [
            MemoryRecordWithProvenance(
                record=record, provenance=self._provenance_links.list_by_record_id(record.record_id)
            )
            for record in records
        ]


class SupersedeMemoryRecordUseCase:
    """User-initiated correction of a Memory Record (Persistent Brain v2: "eventually allow
    correction/removal/supersession according to the frozen rules"). Implements *supersession*
    specifically - the one correction mechanism the frozen model already provides a field for
    (`MemoryRecordStatus.SUPERSEDED`, `superseded_record_id`, `superseded_at`), exercised here
    for the first time since Stage 2. Deliberately does **not** implement deletion/retraction-
    without-replacement: the frozen model documents no "retracted" or "deleted" state for
    Memory Record (only current/superseded), so inventing one here would be silently choosing
    an unreviewed persistence strategy - the same discipline `WritingProfileAlreadyExtractedError`
    already established for an analogous gap (see that exception's docstring). A genuine
    "forget this" capability remains an open, flagged architectural question, not a decision
    made in this pass.

    The replacement record is created with `source_type=USER_INPUT` (Business Rule 4: the user
    correcting their own remembered context *is* the awareness signal - no AI call is involved
    in a correction, unlike the review-approval-triggered extraction pipeline).
    """

    def __init__(
        self,
        memory_record_repository: MemoryRecordRepository,
        memory_provenance_link_repository: MemoryProvenanceLinkRepository,
        agent_repository: AgentRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._memory_records = memory_record_repository
        self._provenance_links = memory_provenance_link_repository
        self._agents = agent_repository
        self._uow = unit_of_work

    def execute(self, *, user_id: int, record_id: int, content: str, rationale: str | None = None) -> MemoryRecord:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        old_record = self._memory_records.get_by_id(record_id)
        if old_record is None or old_record.agent_id != agent.agent_id:
            raise MemoryRecordNotFoundError(record_id=record_id)
        if old_record.status != MemoryRecordStatus.CURRENT:
            raise MemoryRecordAlreadySupersededError(record_id=record_id)

        try:
            new_record = self._memory_records.add(
                MemoryRecord(
                    agent_id=agent.agent_id,
                    record_type=old_record.record_type,
                    content=content,
                    rationale=rationale,
                    created_by=CreatedBy.USER,
                )
            )
            self._provenance_links.add(
                MemoryProvenanceLink(record_id=new_record.record_id, source_type=MemoryProvenanceSourceType.USER_INPUT)
            )
            self._memory_records.mark_superseded(
                record_id, superseded_record_id=new_record.record_id, superseded_at=datetime.now(timezone.utc)
            )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        return new_record
