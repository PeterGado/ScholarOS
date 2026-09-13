from datetime import datetime

from pydantic import BaseModel

from app.modules.writing.application.style_extraction import WritingStyleProfileExtraction
from app.modules.writing.application.style_ingestion import WritingStyleDocumentUpload


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
