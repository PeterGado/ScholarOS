from abc import ABC, abstractmethod

from app.modules.project.domain.entities import Project


class ProjectRepository(ABC):
    @abstractmethod
    def get_by_agent_id(self, agent_id: int) -> Project | None: ...

    @abstractmethod
    def get_by_id(self, project_id: int) -> Project | None: ...

    @abstractmethod
    def add(self, project: Project) -> Project: ...
