from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.exception_handlers import ErrorResponse
from app.core.dependencies import (
    get_current_user_id,
    get_delete_research_document_use_case,
    get_list_project_documents_use_case,
    get_retry_document_processing_use_case,
    get_upload_research_document_use_case,
)
from app.modules.document.application.use_cases import (
    DeleteResearchDocumentUseCase,
    ListProjectDocumentsUseCase,
    RetryDocumentProcessingUseCase,
    UploadResearchDocumentUseCase,
)
from app.modules.document.interface.schemas import ResearchDocumentListResponse, ResearchDocumentResponse

router = APIRouter(prefix="/projects", tags=["documents"])


@router.post(
    "/{project_id}/documents",
    response_model=ResearchDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "The referenced Project does not exist, or does not belong to the authenticated user.",
        },
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
    user_id: int = Depends(get_current_user_id),
    use_case: UploadResearchDocumentUseCase = Depends(get_upload_research_document_use_case),
) -> ResearchDocumentResponse:
    """Upload a Research Document into an existing Project (§10.1; §10.2's documented
    dependency on the project service for project association). Routed by project_id, not
    agent_id, because the underlying use case and the Logical Data Model both scope
    ResearchDocument to Project directly - addressing it that way needs no extra lookup here.

    The authenticated identity (ADR-010, Stage 6) is resolved here and passed to the use
    case as data, never as a client-supplied value - `user_id` participates in ownership
    validation (Project -> Agent -> User), it does not come from the request body or query.

    No business logic lives here: existence/ownership checks, content-store writes, and
    persistence happen in UploadResearchDocumentUseCase; exceptions are translated to HTTP
    responses by the handlers registered in app.api.exception_handlers.
    """
    content = await file.read()
    extension = Path(file.filename).suffix.lstrip(".") if file.filename else ""

    document = use_case.execute(
        project_id=project_id,
        user_id=user_id,
        title=title,
        format=format,
        content=content,
        author=author,
        source=source,
        extension=extension,
    )
    return ResearchDocumentResponse.from_domain(document)


@router.get(
    "/{project_id}/documents",
    response_model=ResearchDocumentListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "The referenced Project does not exist, or does not belong to the authenticated user.",
        },
    },
)
def list_project_documents(
    project_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: ListProjectDocumentsUseCase = Depends(get_list_project_documents_use_case),
) -> ResearchDocumentListResponse:
    """List a Project's Research Documents, most recently used to observe `processing_status`
    (see ListProjectDocumentsUseCase's docstring for why this endpoint was added). A Project
    with no documents yet returns an empty list (200), not a 404 - the Project itself still
    exists and is owned by the caller, mirroring GET /writing/drafts's own precedent.
    """
    documents = use_case.execute(project_id=project_id, user_id=user_id)
    return ResearchDocumentListResponse.from_domain(documents)


@router.delete(
    "/{project_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "No such Project/Document, it does not belong to the authenticated user, or it was already deleted.",
        },
        409: {
            "model": ErrorResponse,
            "description": "The document has already been processed (or is currently processing) and can no longer be deleted.",
        },
    },
)
def delete_research_document(
    project_id: int,
    document_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: DeleteResearchDocumentUseCase = Depends(get_delete_research_document_use_case),
) -> None:
    """Deletes a Research Document that has not yet been successfully processed (`pending` or
    `failed` only - see DeleteResearchDocumentUseCase's docstring). A soft delete: the row and
    its stored content remain, but it disappears from `GET .../documents` and can never be
    listed, generated with, or deleted again.
    """
    use_case.execute(project_id=project_id, user_id=user_id, document_id=document_id)


@router.post(
    "/{project_id}/documents/{document_id}/retry",
    response_model=ResearchDocumentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "No such Project/Document, it does not belong to the authenticated user, or it was deleted.",
        },
        409: {
            "model": ErrorResponse,
            "description": "The document has not failed - only a failed document can be retried.",
        },
    },
)
def retry_document_processing(
    project_id: int,
    document_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: RetryDocumentProcessingUseCase = Depends(get_retry_document_processing_use_case),
) -> ResearchDocumentResponse:
    """Re-enqueues processing for a Research Document whose previous attempt terminally
    `failed` (see RetryDocumentProcessingUseCase's docstring) - lets a document recover from a
    transient failure (e.g. the AI provider's quota was briefly exhausted) without deleting it
    and re-uploading the same file.
    """
    document = use_case.execute(project_id=project_id, user_id=user_id, document_id=document_id)
    return ResearchDocumentResponse.from_domain(document)
