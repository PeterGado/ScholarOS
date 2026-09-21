from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.document.domain.entities import ResearchDocument
from app.modules.writing.application.profile_view import WritingProfileView
from app.modules.writing.application.style_extraction import WritingStyleProfileExtraction
from app.modules.writing.application.style_ingestion import WritingStyleDocumentUpload
from app.modules.writing.application.memory_inspection import MemoryRecordWithProvenance
from app.modules.writing.domain.entities import Conversation, Message
from app.workers.entities import WorkItem


class WritingStyleDocumentResponse(BaseModel):
    """Response for POST /writing/style-profile/documents.

    Mirrors `ResearchDocumentResponse`'s established exclusions (no `content_reference`, no
    `agent_id`/`user_id`) - `document_id`/`profile_id` are exposed because the existing
    convention already exposes analogous internal ids (`ResearchDocumentResponse.document_id`/
    `project_id`), and the client genuinely needs them to reference what was just created.
    """

    document_id: int
    title: str
    author: str | None
    source: str | None
    format: str
    processing_status: str
    ingested_at: datetime
    profile_id: int
    profile_name: str

    @classmethod
    def from_domain(cls, upload: WritingStyleDocumentUpload) -> "WritingStyleDocumentResponse":
        return cls(
            document_id=upload.document.document_id,
            title=upload.document.title,
            author=upload.document.author,
            source=upload.document.source,
            format=upload.document.format,
            processing_status=upload.document.processing_status.value,
            ingested_at=upload.document.ingested_at,
            profile_id=upload.profile.profile_id,
            profile_name=upload.profile.name,
        )


class WritingStyleDocumentSummaryResponse(BaseModel):
    """Response item for GET /writing/style-profile/documents - lets the frontend show what a
    user has already uploaded across sessions (see `ListWritingStyleDocumentsUseCase`'s own
    docstring for the bug this closes). No `processing_status`: a style sample is never
    submitted to the knowledge pipeline, so that field would always read `pending` and imply a
    stuck upload that isn't actually stuck.
    """

    document_id: int
    title: str
    author: str | None
    source: str | None
    format: str
    ingested_at: datetime

    @classmethod
    def from_domain(cls, document: ResearchDocument) -> "WritingStyleDocumentSummaryResponse":
        return cls(
            document_id=document.document_id,
            title=document.title,
            author=document.author,
            source=document.source,
            format=document.format,
            ingested_at=document.ingested_at,
        )


class WritingStyleDocumentListResponse(BaseModel):
    documents: list[WritingStyleDocumentSummaryResponse]

    @classmethod
    def from_domain(cls, documents: list[ResearchDocument]) -> "WritingStyleDocumentListResponse":
        return cls(documents=[WritingStyleDocumentSummaryResponse.from_domain(d) for d in documents])


class ExtractWritingStyleProfileRequest(BaseModel):
    """Request for POST /writing/style-profile/extract. `document_ids` names exactly which
    already-uploaded Research Documents to analyze as style samples (Stage 4 report §4:
    no frozen field distinguishes a style sample from ordinary research material, so the
    caller supplies the set explicitly - the same set returned by prior
    POST /writing/style-profile/documents calls). No agent_id/profile_id is accepted here;
    ownership is resolved entirely from the authenticated identity.
    """

    document_ids: list[int]


class ProfileCharacteristicResponse(BaseModel):
    characteristic_id: int
    characteristic_type: str
    signal: str
    confidence: float | None
    source_document_ids: list[int]


class WritingStyleProfileExtractionResponse(BaseModel):
    profile_id: int
    profile_name: str
    characteristics: list[ProfileCharacteristicResponse]

    @classmethod
    def from_domain(cls, result: WritingStyleProfileExtraction) -> "WritingStyleProfileExtractionResponse":
        return cls(
            profile_id=result.profile.profile_id,
            profile_name=result.profile.name,
            characteristics=[
                ProfileCharacteristicResponse(
                    characteristic_id=item.characteristic.characteristic_id,
                    characteristic_type=item.characteristic.characteristic_type.value,
                    signal=item.characteristic.signal,
                    confidence=item.characteristic.confidence,
                    source_document_ids=item.source_document_ids,
                )
                for item in result.characteristics
            ],
        )


class WritingProfileCharacteristicResponse(BaseModel):
    """Deliberately excludes source_document_ids - unlike the extraction-result response
    (ProfileCharacteristicResponse), a profile-view read has no extraction run in hand to
    attach them to without an additional per-characteristic repository lookup this endpoint
    does not otherwise need (Stage 7 report: deliberate scope boundary).
    """

    characteristic_id: int
    characteristic_type: str
    signal: str
    confidence: float | None


class StartConversationRequest(BaseModel):
    """Request for POST /writing/conversations. No agent_id - resolved from the authenticated
    identity, mirroring every other Writing create endpoint. `title` is a free-form, optional
    label the caller may give the conversation; unset for an untitled chat thread.
    """

    title: str | None = Field(None, max_length=255)


class ConversationResponse(BaseModel):
    conversation_id: int
    title: str | None
    status: str
    started_at: datetime

    @classmethod
    def from_domain(cls, conversation: Conversation) -> "ConversationResponse":
        return cls(
            conversation_id=conversation.conversation_id,
            title=conversation.title,
            status=conversation.status.value,
            started_at=conversation.started_at,
        )


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]

    @classmethod
    def from_domain(cls, conversations: list[Conversation]) -> "ConversationListResponse":
        return cls(conversations=[ConversationResponse.from_domain(c) for c in conversations])


class SendChatMessageRequest(BaseModel):
    # 2026-09-21: no upper bound existed anywhere on a chat message's length - the last open
    # item from the security ledger's "no max request/body size" gap. 8000 characters
    # comfortably covers real multi-paragraph instructions without being an unbounded field a
    # client could use to send an arbitrarily large request body.
    content: str = Field(..., min_length=1, max_length=8000)


class ChatMessageResponse(BaseModel):
    message_id: int
    sequence: int
    direction: str
    content: str
    created_at: datetime

    @classmethod
    def from_domain(cls, message: Message) -> "ChatMessageResponse":
        return cls(
            message_id=message.message_id,
            sequence=message.sequence,
            direction=message.direction.value,
            content=message.content,
            created_at=message.created_at,
        )


class ChatMessageListResponse(BaseModel):
    messages: list[ChatMessageResponse]

    @classmethod
    def from_domain(cls, messages: list[Message]) -> "ChatMessageListResponse":
        return cls(messages=[ChatMessageResponse.from_domain(m) for m in messages])


class ChatReplyStatusResponse(BaseModel):
    """Uses the existing Work Item state contract (app.workers.enums.WorkItemState) - the reply
    is generated asynchronously, by the Work Item executor, never synchronously inside this
    request.
    """

    conversation_id: int
    work_item_id: int
    state: str
    last_error: str | None = None

    @classmethod
    def from_domain(cls, *, conversation_id: int, work_item: WorkItem) -> "ChatReplyStatusResponse":
        return cls(
            conversation_id=conversation_id,
            work_item_id=work_item.work_item_id,
            state=work_item.state.value,
            last_error=work_item.last_error,
        )


class MemoryProvenanceResponse(BaseModel):
    source_type: str
    conversation_id: int | None
    element_id: int | None
    document_id: int | None


class MemoryRecordResponse(BaseModel):
    record_id: int
    record_type: str
    content: str
    rationale: str | None
    status: str
    created_at: datetime
    created_by: str
    provenance: list[MemoryProvenanceResponse]

    @classmethod
    def from_domain(cls, item: MemoryRecordWithProvenance) -> "MemoryRecordResponse":
        return cls(
            record_id=item.record.record_id,
            record_type=item.record.record_type.value,
            content=item.record.content,
            rationale=item.record.rationale,
            status=item.record.status.value,
            created_at=item.record.created_at,
            created_by=item.record.created_by.value,
            provenance=[
                MemoryProvenanceResponse(
                    source_type=link.source_type.value,
                    conversation_id=link.conversation_id,
                    element_id=link.element_id,
                    document_id=link.document_id,
                )
                for link in item.provenance
            ],
        )


class MemoryRecordListResponse(BaseModel):
    records: list[MemoryRecordResponse]

    @classmethod
    def from_domain(cls, items: list[MemoryRecordWithProvenance]) -> "MemoryRecordListResponse":
        return cls(records=[MemoryRecordResponse.from_domain(item) for item in items])


class SupersedeMemoryRecordRequest(BaseModel):
    """Request for POST /memory/{record_id}/supersede. `content` is the corrected memory
    statement the user is asserting, replacing the current one - the user's own correction is
    the awareness signal (Business Rule 4), not an AI call.
    """

    content: str = Field(..., min_length=1)
    rationale: str | None = None


class WritingProfileViewResponse(BaseModel):
    profile_id: int
    profile_name: str
    characteristics: list[WritingProfileCharacteristicResponse]

    @classmethod
    def from_domain(cls, view: WritingProfileView) -> "WritingProfileViewResponse":
        return cls(
            profile_id=view.profile.profile_id,
            profile_name=view.profile.name,
            characteristics=[
                WritingProfileCharacteristicResponse(
                    characteristic_id=c.characteristic_id,
                    characteristic_type=c.characteristic_type.value,
                    signal=c.signal,
                    confidence=c.confidence,
                )
                for c in view.characteristics
            ],
        )
