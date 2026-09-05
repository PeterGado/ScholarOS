from sqlalchemy.orm import Session

from app.modules.project.domain.entities import Project
from app.modules.project.domain.repositories import ProjectRepository
from app.modules.project.infrastructure.models import Project as ProjectModel


class SqlAlchemyProjectRepository(ProjectRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_agent_id(self, agent_id: int) -> Project | None:
        row = self._session.query(ProjectModel).filter_by(agent_id=agent_id).one_or_none()
        return self._to_domain(row) if row is not None else None

    def get_by_id(self, project_id: int) -> Project | None:
        row = self._session.get(ProjectModel, project_id)
        return self._to_domain(row) if row is not None else None

    def add(self, project: Project) -> Project:
        row = ProjectModel(
            agent_id=project.agent_id,
            title=project.title,
            description=project.description,
            topic=project.topic,
            status=project.status,
        )
        self._session.add(row)
        self._session.flush()
        project.project_id = row.project_id
        project.created_at = row.created_at
        return project

    @staticmethod
    def _to_domain(row: ProjectModel) -> Project:
        return Project(
            project_id=row.project_id,
            agent_id=row.agent_id,
            title=row.title,
            description=row.description,
            topic=row.topic,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
            closed_at=row.closed_at,
            deleted_at=row.deleted_at,
        )
