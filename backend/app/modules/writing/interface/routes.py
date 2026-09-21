from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status

from app.api.exception_handlers import ErrorResponse
from app.core.config import get_settings
from app.core.dependencies import (
    get_current_user_id,
    get_extract_writing_style_profile_use_case,
    get_get_chat_reply_status_use_case,
    get_get_writing_profile_use_case,
    get_list_conversation_messages_use_case,
    get_delete_conversation_use_case,
    get_list_conversations_use_case,
    get_list_memory_use_case,
    get_list_writing_style_documents_use_case,
    get_retry_chat_reply_use_case,
    get_send_chat_message_use_case,
    get_start_conversation_use_case,
    get_supersede_memory_record_use_case,
    get_upload_writing_style_document_use_case,
)
from app.core.document_formats import looks_like_a_supported_document
from app.core.exceptions import UnsupportedUploadFormatError
from app.core.rate_limit import limiter
from app.core.uploads import read_upload_within_limit
from app.modules.writing.application.chat import (
    DeleteConversationUseCase,
    GetChatReplyStatusUseCase,
    ListConversationMessagesUseCase,
    ListConversationsUseCase,
    RetryChatReplyUseCase,
    SendChatMessageUseCase,
    StartConversationUseCase,
)
from app.modules.writing.application.memory_inspection import (
    ListMemoryUseCase,
    MemoryRecordWithProvenance,
    SupersedeMemoryRecordUseCase,
)
from app.modules.writing.application.profile_view import GetWritingProfileUseCase
from app.modules.writing.application.style_extraction import ExtractWritingStyleProfileUseCase
from app.modules.writing.application.style_ingestion import (
    ListWritingStyleDocumentsUseCase,
    UploadWritingStyleDocumentUseCase,
)
from app.modules.writing.interface.schemas import (
    ChatMessageListResponse,
    ChatReplyStatusResponse,
    ConversationListResponse,
    ConversationResponse,
    ExtractWritingStyleProfileRequest,
    MemoryRecordListResponse,
    MemoryRecordResponse,
    SendChatMessageRequest,
    StartConversationRequest,
    SupersedeMemoryRecordRequest,
    WritingProfileViewResponse,
    WritingStyleDocumentListResponse,
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
        413: {"model": ErrorResponse, "description": "The uploaded file exceeds the server's maximum allowed size."},
        422: {
            "model": ErrorResponse,
            "description": "Invalid title/format/content, or a file that isn't plain text/.docx/PDF. Malformed request bodies use FastAPI's own validation error shape instead.",
        },
        429: {"model": ErrorResponse, "description": "Too many uploads from this client."},
        500: {"model": ErrorResponse, "description": "Storage failure or unexpected internal failure."},
    },
)
# 2026-09-19 production security pass: same cost profile as /projects/{id}/documents uploads.
@limiter.limit("20/minute")
async def upload_writing_style_document(
    request: Request,
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
    content = await read_upload_within_limit(file, max_bytes=get_settings().max_upload_size_bytes)
    if not looks_like_a_supported_document(content):
        raise UnsupportedUploadFormatError()
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


@router.get(
    "/style-profile/documents",
    response_model=WritingStyleDocumentListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "The authenticated user has no Agent yet."},
    },
)
def list_writing_style_documents(
    user_id: int = Depends(get_current_user_id),
    use_case: ListWritingStyleDocumentsUseCase = Depends(get_list_writing_style_documents_use_case),
) -> WritingStyleDocumentListResponse:
    """List the authenticated user's own already-uploaded writing-style samples (see
    `ListWritingStyleDocumentsUseCase`'s own docstring for the bug this closes). An Agent with
    none uploaded yet returns an empty list (200), not a 404.
    """
    return WritingStyleDocumentListResponse.from_domain(use_case.execute(user_id=user_id))


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
        429: {"model": ErrorResponse, "description": "Too many extraction requests from this client."},
        502: {"model": ErrorResponse, "description": "The AI provider request failed."},
        503: {"model": ErrorResponse, "description": "The AI provider is not configured."},
    },
)
# 2026-09-19 production security pass: this makes a real AI provider call - the most directly
# cost-bearing route in the app alongside chat replies. 10/minute per IP.
@limiter.limit("10/minute")
async def extract_writing_style_profile(
    request: Request,
    payload: ExtractWritingStyleProfileRequest,
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
    result = use_case.execute(user_id=user_id, document_ids=payload.document_ids)
    return WritingStyleProfileExtractionResponse.from_domain(result)


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


# --- Persistent Brain v2: Memory inspection -------------------------------------------------


@router.get(
    "/memory",
    response_model=MemoryRecordListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "The authenticated user has no Agent yet."},
    },
)
def list_memory(
    user_id: int = Depends(get_current_user_id),
    use_case: ListMemoryUseCase = Depends(get_list_memory_use_case),
) -> MemoryRecordListResponse:
    """Lists the authenticated user's own Agent's current Memory Records with provenance
    (Persistent Brain v2: "let the user see what the brain remembers, show provenance"). An
    Agent with no memory yet returns an empty list (200), not a 404.
    """
    return MemoryRecordListResponse.from_domain(use_case.execute(user_id=user_id))


@router.post(
    "/memory/{record_id}/supersede",
    response_model=MemoryRecordResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "No such Memory Record, or it does not belong to the authenticated user.",
        },
        409: {"model": ErrorResponse, "description": "The Memory Record has already been superseded."},
        422: {"model": ErrorResponse, "description": "Blank content."},
    },
)
def supersede_memory_record(
    record_id: int,
    request: SupersedeMemoryRecordRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: SupersedeMemoryRecordUseCase = Depends(get_supersede_memory_record_use_case),
) -> MemoryRecordResponse:
    """User-initiated correction: replaces a current Memory Record's content with a new one the
    user asserts, and marks the old one superseded (Persistent Brain v2 - "eventually allow
    correction... according to the frozen rules"). The new record's provenance is the user's
    own input, not an AI call.
    """
    new_record = use_case.execute(
        user_id=user_id, record_id=record_id, content=request.content, rationale=request.rationale
    )
    # The new record's own provenance link (source_type=user_input) was just created by the use
    # case but isn't returned to avoid an extra repository round trip here - the response shows
    # an empty provenance list for it; a subsequent GET /memory reflects it in full.
    return MemoryRecordResponse.from_domain(MemoryRecordWithProvenance(record=new_record, provenance=[]))


# --- Persistent Brain Decision 3: Agent Workspace chat -------------------------------------


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "The authenticated user has no Agent yet."},
    },
)
def start_conversation(
    request: StartConversationRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: StartConversationUseCase = Depends(get_start_conversation_use_case),
) -> ConversationResponse:
    """Opens a new Agent Workspace conversation (Persistent Brain Decision 3). No agent_id is
    accepted from the client.
    """
    conversation = use_case.execute(user_id=user_id, title=request.title)
    return ConversationResponse.from_domain(conversation)


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "The authenticated user has no Agent yet."},
    },
)
def list_conversations(
    user_id: int = Depends(get_current_user_id),
    use_case: ListConversationsUseCase = Depends(get_list_conversations_use_case),
) -> ConversationListResponse:
    """Lists every Conversation owned by the authenticated user's own Agent."""
    return ConversationListResponse.from_domain(use_case.execute(user_id=user_id))


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "No such Conversation, or it does not belong to the authenticated user, or it was already deleted.",
        },
    },
)
def delete_conversation(
    conversation_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: DeleteConversationUseCase = Depends(get_delete_conversation_use_case),
) -> None:
    """Soft-deletes a Conversation - its Messages are preserved, but it disappears from
    `GET /writing/conversations` and can no longer be read from or sent to.
    """
    use_case.execute(user_id=user_id, conversation_id=conversation_id)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ChatMessageListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "No such Conversation, or it does not belong to the authenticated user.",
        },
    },
)
def list_conversation_messages(
    conversation_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: ListConversationMessagesUseCase = Depends(get_list_conversation_messages_use_case),
) -> ChatMessageListResponse:
    """Lists a Conversation's Messages, oldest first - the client's own chat history view."""
    return ChatMessageListResponse.from_domain(use_case.execute(user_id=user_id, conversation_id=conversation_id))


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatReplyStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "No such Conversation, or it does not belong to the authenticated user.",
        },
        422: {"model": ErrorResponse, "description": "Blank content."},
        429: {"model": ErrorResponse, "description": "Too many messages sent from this client."},
    },
)
# 2026-09-19 production security pass: each message enqueues a real AI provider call (via the
# Work Item executor) - the other most directly cost-bearing route alongside style extraction.
@limiter.limit("20/minute")
def send_chat_message(
    request: Request,
    conversation_id: int,
    payload: SendChatMessageRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: SendChatMessageUseCase = Depends(get_send_chat_message_use_case),
) -> ChatReplyStatusResponse:
    """Sends one chat message and enqueues its reply through the existing Work Item mechanism
    (Persistent Brain Decision 3) - the same asynchronous pattern `POST /writing/drafts/
    {draft_id}/generate` already uses. The message itself is persisted synchronously here;
    the AI reply is generated later, in the Work Item executor, and appears as a new Message
    once `GET /writing/conversations/{conversation_id}/messages` is polled again.
    """
    work_item = use_case.execute(user_id=user_id, conversation_id=conversation_id, content=payload.content)
    return ChatReplyStatusResponse.from_domain(conversation_id=conversation_id, work_item=work_item)


@router.get(
    "/conversations/{conversation_id}/reply-status/{work_item_id}",
    response_model=ChatReplyStatusResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "No such Conversation, or no such Work Item belonging to it.",
        },
    },
)
def get_chat_reply_status(
    conversation_id: int,
    work_item_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: GetChatReplyStatusUseCase = Depends(get_get_chat_reply_status_use_case),
) -> ChatReplyStatusResponse:
    """Lets the client poll a specific reply's real state (`queued`/`running`/`succeeded`/
    `failed`) and, once `failed`, the real reason - instead of only ever inferring completion
    from a new Message appearing (still the fast path on success; this is what closes the gap
    once it doesn't).
    """
    work_item = use_case.execute(user_id=user_id, conversation_id=conversation_id, work_item_id=work_item_id)
    return ChatReplyStatusResponse.from_domain(conversation_id=conversation_id, work_item=work_item)


@router.post(
    "/conversations/{conversation_id}/reply-status/{work_item_id}/retry",
    response_model=ChatReplyStatusResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {
            "model": ErrorResponse,
            "description": "No such Conversation, or no such Work Item belonging to it.",
        },
        409: {
            "model": ErrorResponse,
            "description": "The reply has not failed - only a failed reply can be retried.",
        },
    },
)
def retry_chat_reply(
    conversation_id: int,
    work_item_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: RetryChatReplyUseCase = Depends(get_retry_chat_reply_use_case),
) -> ChatReplyStatusResponse:
    """Re-enqueues a `failed` chat reply generation, mirroring `POST /projects/{project_id}/
    documents/{document_id}/retry`'s established pattern exactly."""
    work_item = use_case.execute(user_id=user_id, conversation_id=conversation_id, work_item_id=work_item_id)
    return ChatReplyStatusResponse.from_domain(conversation_id=conversation_id, work_item=work_item)
