from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.writing.application.profile_view import WritingProfileView
from app.modules.writing.application.style_extraction import WritingStyleProfileExtraction
from app.modules.writing.application.style_ingestion import WritingStyleDocumentUpload
from app.modules.writing.application.use_cases import DraftVersionWithEvidence
from app.modules.writing.domain.entities import Draft, ReviewDecision
from app.modules.writing.domain.enums import ReviewOutcome
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


class CreateDraftRequest(BaseModel):
    """Request for POST /writing/drafts. No agent_id - ownership is resolved entirely from
    the authenticated identity (mirrors CreateAgentWorkspaceRequest's own convention).
    """

    title: str = Field(..., min_length=1, max_length=255)
    target: str | None = None


class DraftResponse(BaseModel):
    """Excludes agent_id - the client never needs it, every writing endpoint is scoped by
    draft_id or the authenticated identity alone.
    """

    draft_id: int
    title: str
    target: str | None
    status: str
    created_at: datetime

    @classmethod
    def from_domain(cls, draft: Draft) -> "DraftResponse":
        return cls(
            draft_id=draft.draft_id,
            title=draft.title,
            target=draft.target,
            status=draft.status.value,
            created_at=draft.created_at,
        )


class DraftListResponse(BaseModel):
    drafts: list[DraftResponse]

    @classmethod
    def from_domain(cls, drafts: list[Draft]) -> "DraftListResponse":
        return cls(drafts=[DraftResponse.from_domain(draft) for draft in drafts])


class DraftEvidenceLinkResponse(BaseModel):
    """Provenance as the writing domain already persists it - no additional lookups (e.g. a
    source document's title) are performed; that would require injecting the Document module's
    repository into a use case that otherwise needs no cross-module dependency beyond what
    Draft Evidence Link itself already stores (Stage 7 report: deliberate scope boundary).
    """

    target_type: str
    chunk_id: int | None
    document_id: int | None


class DraftVersionResponse(BaseModel):
    version_id: int
    version_number: int
    content: str
    created_at: datetime
    created_by: str
    evidence: list[DraftEvidenceLinkResponse]

    @classmethod
    def from_domain(cls, item: DraftVersionWithEvidence) -> "DraftVersionResponse":
        return cls(
            version_id=item.version.version_id,
            version_number=item.version.version_number,
            content=item.version.content,
            created_at=item.version.created_at,
            created_by=item.version.created_by.value,
            evidence=[
                DraftEvidenceLinkResponse(
                    target_type=link.target_type.value, chunk_id=link.chunk_id, document_id=link.document_id
                )
                for link in item.evidence
            ],
        )


class DraftVersionListResponse(BaseModel):
    versions: list[DraftVersionResponse]

    @classmethod
    def from_domain(cls, items: list[DraftVersionWithEvidence]) -> "DraftVersionListResponse":
        return cls(versions=[DraftVersionResponse.from_domain(item) for item in items])


class RequestDraftGenerationRequest(BaseModel):
    """Request for POST /writing/drafts/{draft_id}/generate. Deliberately carries no evidence,
    style, or memory fields - those are resolved server-side by `RequestDraftGenerationUseCase`
    (real retrieval, the Agent's own Writing Profile, the Agent's own Memory Records), never
    accepted from the client (Stage 7 reconnaissance finding - see the use case's docstring).
    """

    instructions: str = Field(..., min_length=1)


class GenerationStatusResponse(BaseModel):
    """Uses the existing Work Item state contract (app.workers.enums.WorkItemState) rather
    than inventing a second asynchronous status model. Excludes payload_reference/
    idempotency_key - internal outbox plumbing (a content-store key), not part of the public
    contract, mirroring ResearchDocumentResponse's own content_reference exclusion.
    """

    draft_id: int
    work_item_id: int
    state: str

    @classmethod
    def from_domain(cls, *, draft_id: int, work_item: WorkItem) -> "GenerationStatusResponse":
        return cls(draft_id=draft_id, work_item_id=work_item.work_item_id, state=work_item.state.value)


class SubmitDraftReviewRequest(BaseModel):
    outcome: ReviewOutcome
    rationale: str | None = None
    notes: str | None = None


class ReviewDecisionResponse(BaseModel):
    decision_id: int
    review_id: int
    outcome: str
    rationale: str | None
    decided_at: datetime

    @classmethod
    def from_domain(cls, decision: ReviewDecision) -> "ReviewDecisionResponse":
        return cls(
            decision_id=decision.decision_id,
            review_id=decision.review_id,
            outcome=decision.outcome.value,
            rationale=decision.rationale,
            decided_at=decision.decided_at,
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
