from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.exception_handlers import ErrorResponse
from app.core.dependencies import (
    get_create_draft_use_case,
    get_current_user_id,
    get_extract_writing_style_profile_use_case,
    get_get_draft_use_case,
    get_get_writing_profile_use_case,
    get_list_draft_versions_use_case,
    get_list_drafts_use_case,
    get_request_draft_generation_use_case,
    get_submit_draft_review_use_case,
    get_upload_writing_style_document_use_case,
)
from app.modules.writing.application.generation_request import RequestDraftGenerationUseCase
from app.modules.writing.application.profile_view import GetWritingProfileUseCase
from app.modules.writing.application.reviews import SubmitDraftReviewUseCase
from app.modules.writing.application.style_extraction import ExtractWritingStyleProfileUseCase
from app.modules.writing.application.style_ingestion import UploadWritingStyleDocumentUseCase
from app.modules.writing.application.use_cases import (
    CreateDraftUseCase,
    GetDraftUseCase,
    ListDraftsUseCase,
    ListDraftVersionsUseCase,
)
from app.modules.writing.interface.schemas import (
    CreateDraftRequest,
    DraftListResponse,
    DraftResponse,
    DraftVersionListResponse,
    ExtractWritingStyleProfileRequest,
    GenerationStatusResponse,
    RequestDraftGenerationRequest,
    ReviewDecisionResponse,
    SubmitDraftReviewRequest,
    WritingProfileViewResponse,
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


@router.post(
    "/drafts",
    response_model=DraftResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "The authenticated user has no Agent yet."},
        422: {"model": ErrorResponse, "description": "Invalid title."},
    },
)
def create_draft(
    request: CreateDraftRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: CreateDraftUseCase = Depends(get_create_draft_use_case),
) -> DraftResponse:
    """Create a Draft (writing task) for the authenticated user's own Agent
    (Project_Writing_Implementation_Plan.md §14). No agent_id is accepted from the client.
    """
    draft = use_case.execute(user_id=user_id, title=request.title, target=request.target)
    return DraftResponse.from_domain(draft)


@router.get(
    "/drafts",
    response_model=DraftListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "The authenticated user has no Agent yet."},
    },
)
def list_drafts(
    user_id: int = Depends(get_current_user_id),
    use_case: ListDraftsUseCase = Depends(get_list_drafts_use_case),
) -> DraftListResponse:
    """List the authenticated user's own Drafts. An Agent with no Drafts yet returns an empty
    list (200) - a different condition from having no Agent at all (404), mirroring
    `GET /knowledge/search`'s own established precedent.
    """
    return DraftListResponse.from_domain(use_case.execute(user_id=user_id))


@router.get(
    "/drafts/{draft_id}",
    response_model=DraftResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "No such Draft, or it does not belong to the authenticated user."},
    },
)
def get_draft(
    draft_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: GetDraftUseCase = Depends(get_get_draft_use_case),
) -> DraftResponse:
    """Fetch one Draft. A Draft owned by a different Agent is reported identically to a
    genuinely missing Draft (non-enumeration).
    """
    return DraftResponse.from_domain(use_case.execute(user_id=user_id, draft_id=draft_id))


@router.post(
    "/drafts/{draft_id}/generate",
    response_model=GenerationStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "No such Draft, or it does not belong to the authenticated user."},
        422: {"model": ErrorResponse, "description": "Blank instructions, or no supporting research evidence was found."},
        502: {"model": ErrorResponse, "description": "The AI provider request failed."},
        503: {"model": ErrorResponse, "description": "The AI provider is not configured."},
    },
)
def request_draft_generation(
    draft_id: int,
    request: RequestDraftGenerationRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: RequestDraftGenerationUseCase = Depends(get_request_draft_generation_use_case),
) -> GenerationStatusResponse:
    """Enqueue asynchronous Draft Version generation through the existing Work Item mechanism
    (Stage 6; ADR-006). The actual AI generation call never happens inside this request - a
    real retrieval search (existing `SearchKnowledgeUseCase`) resolves supporting evidence
    synchronously here (cheap, local, the same pattern `GET /knowledge/search` already uses),
    but the LLM drafting call itself happens later, in the Work Item executor. The response
    reflects the freshly-enqueued Work Item's own state (`queued`) - the existing Work Item
    contract, not a second status model.
    """
    work_item = use_case.execute(user_id=user_id, draft_id=draft_id, instructions=request.instructions)
    return GenerationStatusResponse.from_domain(draft_id=draft_id, work_item=work_item)


@router.get(
    "/drafts/{draft_id}/versions",
    response_model=DraftVersionListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "No such Draft, or it does not belong to the authenticated user."},
    },
)
def list_draft_versions(
    draft_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: ListDraftVersionsUseCase = Depends(get_list_draft_versions_use_case),
) -> DraftVersionListResponse:
    """List a Draft's immutable Draft Versions, oldest first, each with the Draft Evidence
    Links that support it. A Draft that has never been generated returns an empty list (200),
    not a 404 - the Draft itself still exists and is owned by the caller.
    """
    return DraftVersionListResponse.from_domain(use_case.execute(user_id=user_id, draft_id=draft_id))


@router.post(
    "/drafts/{draft_id}/versions/{version_id}/reviews",
    response_model=ReviewDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "No such Draft/Draft Version, or it does not belong to the authenticated user.",
        },
        422: {"model": ErrorResponse, "description": "Invalid outcome. Malformed bodies use FastAPI's own validation error shape."},
    },
)
def submit_draft_review(
    draft_id: int,
    version_id: int,
    request: SubmitDraftReviewRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: SubmitDraftReviewUseCase = Depends(get_submit_draft_review_use_case),
) -> ReviewDecisionResponse:
    """Open a Review and record its Decision in one call (Project_Writing_Implementation_
    Plan.md §14: "Open a Review with a decision"). An `approved` or `revisions_requested`
    outcome also transitions the Draft's own status, per the frozen lifecycle table
    (05_Constraints_and_Integrity.md); `rejected` has no documented Draft-level transition and
    deliberately leaves Draft status unchanged.
    """
    decision = use_case.execute(
        user_id=user_id,
        draft_id=draft_id,
        version_id=version_id,
        outcome=request.outcome,
        rationale=request.rationale,
        notes=request.notes,
    )
    return ReviewDecisionResponse.from_domain(decision)


@router.get(
    "/style-profile",
    response_model=WritingProfileViewResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "The authenticated user has no Agent yet, or their Agent has no active Writing Profile yet.",
        },
    },
)
def get_writing_profile(
    user_id: int = Depends(get_current_user_id),
    use_case: GetWritingProfileUseCase = Depends(get_get_writing_profile_use_case),
) -> WritingProfileViewResponse:
    """Fetch the authenticated user's own Agent's active Writing Profile and its
    characteristics."""
    return WritingProfileViewResponse.from_domain(use_case.execute(user_id=user_id))
