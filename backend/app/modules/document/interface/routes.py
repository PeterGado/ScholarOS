from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.exception_handlers import ErrorResponse
from app.core.dependencies import get_upload_research_document_use_case
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.interface.schemas import ResearchDocumentResponse

router = APIRouter(prefix="/projects", tags=["documents"])


@router.post(
    "/{project_id}/documents",
    response_model=ResearchDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse, "description": "The referenced Project does not exist."},
        422: {
            "model": ErrorResponse,
            "description": "Invalid title/format/content. Malformed request bodies use FastAPI's own validation error shape instead.",
        },
        500: {"model": ErrorResponse, "description": "Storage failure or unexpected internal failure."},
    },
)
async def upload_research_document(
    project_id: int,
    file: UploadFile = File(...),
    title: str = Form(...),
    format: str = Form(...),
    author: str | None = Form(None),
    source: str | None = Form(None),
    use_case: UploadResearchDocumentUseCase = Depends(get_upload_research_document_use_case),
) -> ResearchDocumentResponse:
    """Upload a Research Document into an existing Project (§10.1; §10.2's documented
    dependency on the project service for project association). Routed by project_id, not
    agent_id, because the underlying use case and the Logical Data Model both scope
    ResearchDocument to Project directly - addressing it that way needs no extra lookup here.

    No business logic lives here: existence checks, content-store writes, and persistence
    happen in UploadResearchDocumentUseCase; exceptions are translated to HTTP responses by
    the handlers registered in app.api.exception_handlers.
    """
    content = await file.read()
    extension = Path(file.filename).suffix.lstrip(".") if file.filename else ""

    document = use_case.execute(
        project_id=project_id,
        title=title,
        format=format,
        content=content,
        author=author,
        source=source,
        extension=extension,
    )
    return ResearchDocumentResponse.from_domain(document)
