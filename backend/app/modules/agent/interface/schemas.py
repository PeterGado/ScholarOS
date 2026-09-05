from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.agent.application.use_cases import AgentWorkspace


class CreateAgentWorkspaceRequest(BaseModel):
    """Request body for POST /agents. Topic is supplied at Agent-creation time and becomes
    the single source of truth for the workspace's specialization (ADR-009) - Agent itself
    carries no topic field.
    """

    project_title: str = Field(..., min_length=1, max_length=255)
    project_topic: str = Field(..., min_length=1)
    project_description: str | None = None


class AgentResponse(BaseModel):
    agent_id: int
    status: str
    created_at: datetime


class ProjectResponse(BaseModel):
    project_id: int
    agent_id: int
    title: str
    topic: str
    description: str | None
    status: str
    created_at: datetime


class AgentWorkspaceResponse(BaseModel):
    """Response for POST /agents: the Agent and its one, permanent Project (ADR-009)."""

    agent: AgentResponse
    project: ProjectResponse

    @classmethod
    def from_domain(cls, workspace: AgentWorkspace) -> "AgentWorkspaceResponse":
        return cls(
            agent=AgentResponse(
                agent_id=workspace.agent.agent_id,
                status=workspace.agent.status.value,
                created_at=workspace.agent.created_at,
            ),
            project=ProjectResponse(
                project_id=workspace.project.project_id,
                agent_id=workspace.project.agent_id,
                title=workspace.project.title,
                topic=workspace.project.topic,
                description=workspace.project.description,
                status=workspace.project.status.value,
                created_at=workspace.project.created_at,
            ),
        )
