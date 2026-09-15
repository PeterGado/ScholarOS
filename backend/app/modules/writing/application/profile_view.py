from dataclasses import dataclass

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
