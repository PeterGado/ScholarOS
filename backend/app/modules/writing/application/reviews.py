from datetime import datetime, timezone

from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.writing.domain.entities import Review, ReviewDecision
from app.modules.writing.domain.enums import DraftStatus, ReviewOutcome, ReviewStatus
from app.modules.writing.domain.exceptions import DraftNotFoundError, DraftVersionNotFoundError
from app.modules.writing.domain.repositories import (
    DraftRepository,
    DraftVersionRepository,
    ReviewDecisionRepository,
    ReviewRepository,
)

_DOCUMENTED_DRAFT_STATUS_FOR_OUTCOME = {
    ReviewOutcome.APPROVED: DraftStatus.APPROVED,
    ReviewOutcome.REVISIONS_REQUESTED: DraftStatus.DRAFTING,
}
"""05_Constraints_and_Integrity.md's documented Draft lifecycle only names two review-driven
transitions ("in_review -> approved"; "in_review -> drafting (revision requested)").
`rejected` has no documented Draft-level transition, so it is deliberately absent here - Draft
status is left unchanged for that outcome rather than guessing one (same position the Stage 2
completion report took for this exact ambiguity).
"""


class SubmitDraftReviewUseCase:
    """Opens a Review and records its Decision in one atomic call
    (Project_Writing_Implementation_Plan.md §14: "Open a Review with a decision"). The MVP
    flow never leaves a Review open-without-a-decision, so the Review is persisted directly
    in its already-decided state rather than needing a separate "open" step and a
    status-update repository method - `05_Constraints_and_Integrity.md` invariant 7 ("at most
    one open Review per Draft Version") is therefore never at risk here, since no row this
    use case creates is ever left in the `open` state.
    """

    def __init__(
        self,
        draft_repository: DraftRepository,
        draft_version_repository: DraftVersionRepository,
        review_repository: ReviewRepository,
        review_decision_repository: ReviewDecisionRepository,
        agent_repository: AgentRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._drafts = draft_repository
        self._versions = draft_version_repository
        self._reviews = review_repository
        self._decisions = review_decision_repository
        self._agents = agent_repository
        self._uow = unit_of_work

    def execute(
        self,
        *,
        user_id: int,
        draft_id: int,
        version_id: int,
        outcome: ReviewOutcome,
        rationale: str | None = None,
        notes: str | None = None,
    ) -> ReviewDecision:
        draft = self._drafts.get_by_id(draft_id)
        agent = self._agents.get_by_id(draft.agent_id) if draft is not None else None
        if draft is None or agent is None or agent.user_id != user_id:
            raise DraftNotFoundError(draft_id=draft_id)

        version = self._versions.get_by_id(version_id)
        if version is None or version.draft_id != draft_id:
            raise DraftVersionNotFoundError(version_id=version_id)

        try:
            review = self._reviews.add(
                Review(
                    draft_version_id=version_id,
                    status=ReviewStatus.DECIDED,
                    notes=notes,
                    decided_at=datetime.now(timezone.utc),
                )
            )
            decision = self._decisions.add(
                ReviewDecision(review_id=review.review_id, outcome=outcome, decided_by=user_id, rationale=rationale)
            )
            new_status = _DOCUMENTED_DRAFT_STATUS_FOR_OUTCOME.get(outcome)
            if new_status is not None:
                self._drafts.update_status(draft_id, new_status)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        return decision
