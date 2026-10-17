from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status

from app.api.exception_handlers import ErrorResponse
from app.core.config import get_settings
from app.core.dependencies import (
    get_current_user_id,
    get_delete_research_document_use_case,
    get_import_external_source_use_case,
    get_list_project_documents_use_case,
    get_retry_document_processing_use_case,
    get_search_external_sources_use_case,
    get_upload_research_document_use_case,
)
from app.core.document_formats import looks_like_a_supported_document
from app.core.exceptions import MaliciousUploadError, UnsupportedUploadFormatError
from app.core.pagination import DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT
from app.core.rate_limit import limiter
from app.core.uploads import read_upload_within_limit
from app.core.virus_scan import is_known_malicious
from app.modules.document.application.use_cases import (
    DeleteResearchDocumentUseCase,
    ImportExternalSourceUseCase,
    ListProjectDocumentsUseCase,
    RetryDocumentProcessingUseCase,
    SearchExternalSourcesUseCase,
    UploadResearchDocumentUseCase,
)
from app.modules.document.interface.schemas import (
    ExternalSourceSearchResponse,
    ImportExternalSourceRequest,
    ResearchDocumentListResponse,
    ResearchDocumentResponse,
)

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
        413: {"model": ErrorResponse, "description": "The uploaded file exceeds the server's maximum allowed size."},
        422: {
            "model": ErrorResponse,
            "description": "Invalid title/format/content, a file that isn't plain text/.docx/PDF, or (only when VirusTotal scanning is configured) a known-malicious file. Malformed request bodies use FastAPI's own validation error shape instead.",
        },
        429: {"model": ErrorResponse, "description": "Too many uploads from this client."},
        500: {"model": ErrorResponse, "description": "Storage failure or unexpected internal failure."},
    },
)
# 2026-09-19 production security pass: an upload triggers real processing work (the Knowledge
# Processing Pipeline, ADR-006) - 20/minute per IP bounds that cost without hindering normal use.
@limiter.limit("20/minute")
async def upload_research_document(
    request: Request,
    project_id: int,
    file: UploadFile = File(...),
    title: str = Form(...),
    format: str = Form(...),
    author: str | None = Form(None),
    source: str | None = Form(None),
    publication_year: int | None = Form(None, ge=1000, le=2100),
    doi: str | None = Form(None),
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
    content = await read_upload_within_limit(file, max_bytes=get_settings().max_upload_size_bytes)
    if not looks_like_a_supported_document(content):
        raise UnsupportedUploadFormatError()
    settings = get_settings()
    if settings.virustotal_api_key and is_known_malicious(content, api_key=settings.virustotal_api_key):
        raise MaliciousUploadError()
    extension = Path(file.filename).suffix.lstrip(".") if file.filename else ""

    document = use_case.execute(
        project_id=project_id,
        user_id=user_id,
        title=title,
        format=format,
        content=content,
        author=author,
        source=source,
        publication_year=publication_year,
        doi=doi,
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
    limit: int = Query(DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    use_case: ListProjectDocumentsUseCase = Depends(get_list_project_documents_use_case),
) -> ResearchDocumentListResponse:
    """List a Project's Research Documents, most recently used to observe `processing_status`
    (see ListProjectDocumentsUseCase's docstring for why this endpoint was added). A Project
    with no documents yet returns an empty list (200), not a 404 - the Project itself still
    exists and is owned by the caller, mirroring GET /writing/drafts's own precedent.
    """
    documents, has_more = use_case.execute(project_id=project_id, user_id=user_id, limit=limit, offset=offset)
    return ResearchDocumentListResponse.from_domain(documents, has_more=has_more)


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


@router.get(
    "/source-search",
    response_model=ExternalSourceSearchResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        422: {"model": ErrorResponse, "description": "Malformed request (empty query)."},
        429: {"model": ErrorResponse, "description": "Too many searches from this client."},
        503: {
            "model": ErrorResponse,
            "description": "External source search is not configured, or OpenAlex is temporarily unavailable.",
        },
    },
)
# A real external API call per search (OpenAlex), not free-form crawling - 10/minute is
# generous for a human searching, tight for a scripted scraping loop against OpenAlex through
# this app's own key.
@limiter.limit("10/minute")
def search_external_sources(
    request: Request,
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=25),
    user_id: int = Depends(get_current_user_id),
    use_case: SearchExternalSourcesUseCase = Depends(get_search_external_sources_use_case),
) -> ExternalSourceSearchResponse:
    """Search-and-import source discovery (2026-10-17): searches OpenAlex's scholarly index for
    candidate sources - NotebookLM-style, a curated list of specific, named results the user
    explicitly chooses from, never an unrestricted crawl of the open web. Not project-scoped:
    this searches a public external index, not anything the authenticated user owns.

    No business logic lives here: the real search call and its failure modes are handled by
    SearchExternalSourcesUseCase; exceptions are translated to HTTP responses by the handlers
    registered in app.api.exception_handlers.
    """
    results = use_case.execute(query=query, limit=limit)
    return ExternalSourceSearchResponse.from_domain(results)


@router.post(
    "/{project_id}/documents/import",
    response_model=ResearchDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "The referenced Project does not exist, does not belong to the authenticated user, or the selected source could no longer be found.",
        },
        409: {"model": ErrorResponse, "description": "The project already has the maximum number of research documents."},
        422: {
            "model": ErrorResponse,
            "description": "The selected source has no open-access full text or abstract available to import.",
        },
        429: {"model": ErrorResponse, "description": "Too many imports from this client."},
        503: {
            "model": ErrorResponse,
            "description": "External source search is not configured, or OpenAlex is temporarily unavailable.",
        },
    },
)
# Same cost profile as a regular upload (triggers the real Knowledge Processing Pipeline) plus
# a real external fetch - 20/minute mirrors upload_research_document's own limit.
@limiter.limit("20/minute")
def import_external_source(
    request: Request,
    project_id: int,
    payload: ImportExternalSourceRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: ImportExternalSourceUseCase = Depends(get_import_external_source_use_case),
) -> ResearchDocumentResponse:
    """Imports a previously-searched OpenAlex result as a real Research Document (2026-10-17) -
    the second half of search-and-import source discovery, and a second on-ramp into the same
    Knowledge Processing Pipeline POST /{project_id}/documents already starts.

    No business logic lives here: re-resolving the source, fetching its content (or falling
    back to its abstract), ownership/cap/email-verification checks, and Work Item enqueueing
    all happen in ImportExternalSourceUseCase; exceptions are translated to HTTP responses by
    the handlers registered in app.api.exception_handlers.
    """
    document = use_case.execute(project_id=project_id, user_id=user_id, openalex_id=payload.openalex_id)
    return ResearchDocumentResponse.from_domain(document)
