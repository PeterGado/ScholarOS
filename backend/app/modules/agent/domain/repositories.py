from abc import ABC, abstractmethod

from app.modules.agent.domain.entities import Agent


class AgentRepository(ABC):
    @abstractmethod
    def get_by_user_id(self, user_id: int) -> Agent | None: ...

    @abstractmethod
    def get_by_id(self, agent_id: int) -> Agent | None: ...

    @abstractmethod
    def add(self, agent: Agent) -> Agent: ...
