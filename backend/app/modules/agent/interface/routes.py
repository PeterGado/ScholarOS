from fastapi import APIRouter, Depends, status

from app.api.exception_handlers import ErrorResponse
from app.core.dependencies import (
    get_create_agent_workspace_use_case,
    get_current_user_id,
    get_get_agent_workspace_use_case,
    get_reset_agent_workspace_use_case,
)
from app.modules.agent.application.reset_workspace import ResetAgentWorkspaceUseCase
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase, GetAgentWorkspaceUseCase
from app.modules.agent.interface.schemas import (
    AgentWorkspaceResponse,
    CreateAgentWorkspaceRequest,
    ResetAgentWorkspaceRequest,
)

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


@router.get(
    "",
    response_model=AgentWorkspaceResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "The authenticated user has no Agent yet."},
    },
)
def get_agent_workspace(
    user_id: int = Depends(get_current_user_id),
    use_case: GetAgentWorkspaceUseCase = Depends(get_get_agent_workspace_use_case),
) -> AgentWorkspaceResponse:
    """Fetch the caller's existing Agent workspace (Agent + its one Project). Added so a
    client can discover its own agent_id/project_id after the initial POST /agents response
    (e.g. after a reload) - see GetAgentWorkspaceUseCase's docstring.
    """
    workspace = use_case.execute(user_id=user_id)
    return AgentWorkspaceResponse.from_domain(workspace)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "The authenticated user has no Agent yet."},
        422: {"model": ErrorResponse, "description": "`confirm` was missing or not `true`."},
    },
)
def reset_agent_workspace(
    payload: ResetAgentWorkspaceRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: ResetAgentWorkspaceUseCase = Depends(get_reset_agent_workspace_use_case),
) -> None:
    """Permanently and irreversibly deletes the authenticated user's entire Agent Workspace -
    Project, documents, knowledge, drafts, writing profile, memory, and conversations - so
    `POST /agents` can be called again for a fresh onboarding. Requires `{"confirm": true}` in
    the body; the frontend is expected to have already confirmed with the user before calling
    this at all.
    """
    use_case.execute(user_id=user_id)
