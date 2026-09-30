from datetime import datetime, timezone
from dataclasses import dataclass

from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.writing.domain.entities import ProfileCharacteristic, WritingProfile
from app.modules.writing.domain.exceptions import WritingProfileNotFoundError
from app.modules.writing.domain.repositories import ProfileCharacteristicRepository, WritingProfileRepository


@dataclass
class WritingProfileView:
    """The Agent's active Writing Profile bundled with its characteristics - `GET
    /writing/style-profile`'s read shape, so the interface layer never makes a second
    repository call itself (mirrors `DraftVersionWithEvidence`'s own reasoning).
    """

    profile: WritingProfile
    characteristics: list[ProfileCharacteristic]


class GetWritingProfileUseCase:
    """Fetches the authenticated user's own Agent's active Writing Profile (05_Constraints_
    and_Integrity.md invariant 8: at most one active profile per Agent). An Agent that exists
    but has never uploaded a style sample yet has no active profile - reported as
    `WritingProfileNotFoundError` (404), a normal, expected pre-Stage-3 state, not an error
    condition mistaken for a missing Agent.
    """

    def __init__(
        self,
        writing_profile_repository: WritingProfileRepository,
        profile_characteristic_repository: ProfileCharacteristicRepository,
        agent_repository: AgentRepository,
    ) -> None:
        self._writing_profiles = writing_profile_repository
        self._profile_characteristics = profile_characteristic_repository
        self._agents = agent_repository

    def execute(self, *, user_id: int) -> WritingProfileView:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        profile = self._writing_profiles.get_active_by_agent_id(agent.agent_id)
        if profile is None:
            raise WritingProfileNotFoundError(agent_id=agent.agent_id)

        characteristics = self._profile_characteristics.list_by_profile_id(profile.profile_id)
        return WritingProfileView(profile=profile, characteristics=characteristics)


class ResetWritingProfileUseCase:
    """Deactivates the authenticated user's own Agent's active Writing Profile so a fresh one
    can be extracted from scratch (2026-09-30, added after a real incident: an extraction that
    slipped past the "do not reproduce sample text verbatim" prompt instruction leaked a
    sample's actual content into a characteristic's `signal`, and every future chat reply kept
    including it as WRITING STYLE AND TONE guidance regardless of topic - derailing unrelated
    writing toward the leaked sample's own subject matter. `ExtractWritingStyleProfileUseCase`
    already refuses to run a second time against a profile that has characteristics
    (`WritingProfileAlreadyExtractedError`, a deliberate, documented decision - see that class's
    own docstring on why regeneration semantics were left unresolved), so there was previously
    no way to recover from a bad extraction short of `DELETE /agents/me`, which destroys the
    entire workspace - every document, conversation, and memory, not just the profile.

    Deactivates, never deletes (mirrors this codebase's established "never tombstoned, only
    superseded" discipline for Memory Records and Conversations): the old profile and its
    characteristics remain in the database exactly as they are, simply no longer active, so
    `get_active_by_agent_id` stops returning them to every future chat prompt. Once deactivated,
    `POST /writing/style-profile/extract` sees no active profile and creates a brand new one,
    exactly as it does for an Agent that has never extracted a profile at all.
    """

    def __init__(
        self,
        writing_profile_repository: WritingProfileRepository,
        agent_repository: AgentRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._writing_profiles = writing_profile_repository
        self._agents = agent_repository
        self._uow = unit_of_work

    def execute(self, *, user_id: int) -> None:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        profile = self._writing_profiles.get_active_by_agent_id(agent.agent_id)
        if profile is None:
            raise WritingProfileNotFoundError(agent_id=agent.agent_id)

        try:
            self._writing_profiles.deactivate(profile.profile_id, updated_at=datetime.now(timezone.utc))
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
