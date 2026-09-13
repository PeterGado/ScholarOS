from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.exception_handlers import ErrorResponse
from app.core.dependencies import (
    get_current_user_id,
    get_extract_writing_style_profile_use_case,
    get_upload_writing_style_document_use_case,
)
from app.modules.writing.application.style_extraction import ExtractWritingStyleProfileUseCase
from app.modules.writing.application.style_ingestion import UploadWritingStyleDocumentUseCase
from app.modules.writing.interface.schemas import (
    ExtractWritingStyleProfileRequest,
    WritingStyleDocumentResponse,
    WritingStyleProfileExtractionResponse,
)

router = APIRouter(prefix="/writing", tags=["writing"])


@router.post(
    "/style-profile/documents",
    response_model=WritingStyleDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "The authenticated user has no Agent yet."},
        422: {
            "model": ErrorResponse,
            "description": "Invalid title/format/content. Malformed request bodies use FastAPI's own validation error shape instead.",
        },
        500: {"model": ErrorResponse, "description": "Storage failure or unexpected internal failure."},
    },
)
async def upload_writing_style_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    format: str = Form(...),
    author: str | None = Form(None),
    source: str | None = Form(None),
    user_id: int = Depends(get_current_user_id),
    use_case: UploadWritingStyleDocumentUseCase = Depends(get_upload_writing_style_document_use_case),
) -> WritingStyleDocumentResponse:
    """Accept a writing-style source document for the authenticated user's own Writing
    Profile (Stage 3 of Project Writing; SRS WR-010). No `agent_id`/`project_id`/`profile_id`
    is accepted from the client - the Agent, its one Project, and its Writing Profile
    (created on first upload if none exists yet) are all resolved server-side from the
    authenticated identity (ADR-010), the same ownership principle already established for
    `POST /projects/{project_id}/documents`.

    No AI call, no retrieval, no Work Item, and no semantic style extraction happens here -
    this endpoint only accepts and persists source material for a later stage.
    """
    content = await file.read()
    extension = Path(file.filename).suffix.lstrip(".") if file.filename else ""

    upload = use_case.execute(
        user_id=user_id,
        title=title,
        format=format,
        content=content,
        author=author,
        source=source,
        extension=extension,
    )
    return WritingStyleDocumentResponse.from_domain(upload)


@router.post(
    "/style-profile/extract",
    response_model=WritingStyleProfileExtractionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "The authenticated user has no Agent yet, or a referenced document_id is not a usable sample for this Agent.",
        },
        409: {"model": ErrorResponse, "description": "This Writing Profile already has extracted characteristics."},
        422: {"model": ErrorResponse, "description": "No document_ids supplied, or a sample's content could not be used."},
        502: {"model": ErrorResponse, "description": "The AI provider request failed."},
        503: {"model": ErrorResponse, "description": "The AI provider is not configured."},
    },
)
async def extract_writing_style_profile(
    request: ExtractWritingStyleProfileRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: ExtractWritingStyleProfileUseCase = Depends(get_extract_writing_style_profile_use_case),
) -> WritingStyleProfileExtractionResponse:
    """Stage 4 of Project Writing: derive real Profile Characteristics from already-uploaded
    writing-style samples via the existing TextGenerationProvider (SRS WR-010/WR-011). The
    caller names exactly which of their own previously-uploaded document_ids to analyze - no
    field on Research Document distinguishes a style sample otherwise (Stage 4 report §4).
    Ownership is resolved entirely from the authenticated identity, never from the request
    body. Running this twice against a profile that already has characteristics is refused
    (409) - the frozen model specifies no regeneration semantics for Profile Characteristic
    yet (Stage 4 report, Deviations).
    """
    result = use_case.execute(user_id=user_id, document_ids=request.document_ids)
    return WritingStyleProfileExtractionResponse.from_domain(result)
