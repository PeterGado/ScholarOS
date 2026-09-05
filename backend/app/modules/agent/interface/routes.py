from fastapi import APIRouter, Depends, status

from app.api.exception_handlers import ErrorResponse
from app.core.dependencies import get_create_agent_workspace_use_case, get_current_user_id
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.interface.schemas import AgentWorkspaceResponse, CreateAgentWorkspaceRequest

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post(
    "",
    response_model=AgentWorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorResponse, "description": "The caller already owns an Agent (one Agent per user, MVP)."},
        422: {
            "model": ErrorResponse,
            "description": "Invalid project title/topic. Malformed request bodies use FastAPI's own validation error shape instead.",
        },
        500: {"model": ErrorResponse, "description": "Unexpected internal failure."},
    },
)
def create_agent_workspace(
    payload: CreateAgentWorkspaceRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: CreateAgentWorkspaceUseCase = Depends(get_create_agent_workspace_use_case),
) -> AgentWorkspaceResponse:
    """Create the caller's Agent together with its one, permanent Project (§22.1; ADR-009).

    No business logic lives here: validation and orchestration happen in
    CreateAgentWorkspaceUseCase; domain/application exceptions are translated to HTTP
    responses by the handlers registered in app.api.exception_handlers.
    """
    workspace = use_case.execute(
        user_id=user_id,
        project_title=payload.project_title,
        project_topic=payload.project_topic,
        project_description=payload.project_description,
    )
    return AgentWorkspaceResponse.from_domain(workspace)
