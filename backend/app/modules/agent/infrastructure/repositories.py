from sqlalchemy.orm import Session

from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.agent.infrastructure.models import Agent as AgentModel


class SqlAlchemyAgentRepository(AgentRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user_id(self, user_id: int) -> Agent | None:
        row = self._session.query(AgentModel).filter_by(user_id=user_id).one_or_none()
        return self._to_domain(row) if row is not None else None

    def get_by_id(self, agent_id: int) -> Agent | None:
        row = self._session.get(AgentModel, agent_id)
        return self._to_domain(row) if row is not None else None

    def add(self, agent: Agent) -> Agent:
        row = AgentModel(user_id=agent.user_id, status=agent.status)
        self._session.add(row)
        self._session.flush()
        agent.agent_id = row.agent_id
        agent.created_at = row.created_at
        return agent

    @staticmethod
    def _to_domain(row: AgentModel) -> Agent:
        return Agent(
            agent_id=row.agent_id,
            user_id=row.user_id,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=row.deleted_at,
        )
