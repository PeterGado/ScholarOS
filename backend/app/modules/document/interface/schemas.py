from datetime import datetime

from pydantic import BaseModel, Field

from app.ai.openalex import OpenAlexWork
from app.ai.tavily import WebSearchResult
from app.modules.document.application.use_cases import ResearchDocumentWithError
from app.modules.document.domain.entities import ResearchDocument


class ResearchDocumentResponse(BaseModel):
    """Response for POST /projects/{project_id}/documents and GET .../documents.

    `content_reference` (the object-store key) is deliberately excluded: it is a storage
    implementation detail, not part of the public contract (ADR-008). `error_message` is
    always null except for a `failed` document, where it carries the underlying Work Item's
    `last_error` - so a user can tell an unsupported-format problem from a transient AI-provider
    outage instead of just seeing "failed" with no explanation.
    """

    document_id: int
    project_id: int
    title: str
    author: str | None
    source: str | None
    publication_year: int | None
    doi: str | None
    doi_verification_status: str | None
    format: str
    processing_status: str
    ingested_at: datetime
    error_message: str | None = None

    @classmethod
    def from_domain(cls, document: ResearchDocument, *, error_message: str | None = None) -> "ResearchDocumentResponse":
        return cls(
            document_id=document.document_id,
            project_id=document.project_id,
            title=document.title,
            author=document.author,
            source=document.source,
            publication_year=document.publication_year,
            doi=document.doi,
            doi_verification_status=document.doi_verification_status.value if document.doi_verification_status else None,
            format=document.format,
            processing_status=document.processing_status.value,
            ingested_at=document.ingested_at,
            error_message=error_message,
        )


class ResearchDocumentListResponse(BaseModel):
    documents: list[ResearchDocumentResponse]
    has_more: bool = False

    @classmethod
    def from_domain(
        cls, documents: list[ResearchDocumentWithError], *, has_more: bool = False
    ) -> "ResearchDocumentListResponse":
        return cls(
            documents=[
                ResearchDocumentResponse.from_domain(item.document, error_message=item.error_message)
                for item in documents
            ],
            has_more=has_more,
        )


class ExternalSourceResponse(BaseModel):
    """One OpenAlex search result (2026-10-17, search-and-import source discovery) - a
    candidate the user may choose to import, not yet a Research Document. `openalex_id` is the
    only field the import request actually needs to carry back (app.ai.openalex.
    get_openalex_work_by_id re-resolves everything else server-side at import time); the rest
    is shown so the user can judge the result before importing it.
    """

    openalex_id: str
    doi: str | None
    title: str
    authors: list[str]
    publication_year: int | None
    source_name: str | None
    is_open_access: bool
    has_fetchable_full_text: bool
    abstract: str | None

    @classmethod
    def from_domain(cls, work: OpenAlexWork) -> "ExternalSourceResponse":
        return cls(
            openalex_id=work.openalex_id,
            doi=work.doi,
            title=work.title,
            authors=list(work.authors),
            publication_year=work.publication_year,
            source_name=work.source_name,
            is_open_access=work.is_open_access,
            has_fetchable_full_text=work.fetchable_url is not None,
            abstract=work.abstract,
        )


class ExternalSourceSearchResponse(BaseModel):
    results: list[ExternalSourceResponse]

    @classmethod
    def from_domain(cls, works: list[OpenAlexWork]) -> "ExternalSourceSearchResponse":
        return cls(results=[ExternalSourceResponse.from_domain(work) for work in works])


class ImportExternalSourceRequest(BaseModel):
    openalex_id: str = Field(..., min_length=1)


class WebSearchResultResponse(BaseModel):
    """One Tavily search result (2026-10-17, general web search discovery) - a candidate the
    user may choose to import, not yet a Research Document. Unlike ExternalSourceResponse,
    `url` and `title` travel back to the import request as-is (see app.ai.tavily.WebSearchResult's
    own docstring for why there is no ID to re-resolve server-side here).
    """

    url: str
    title: str
    snippet: str | None

    @classmethod
    def from_domain(cls, result: WebSearchResult) -> "WebSearchResultResponse":
        return cls(url=result.url, title=result.title, snippet=result.snippet)


class WebSearchResponse(BaseModel):
    results: list[WebSearchResultResponse]

    @classmethod
    def from_domain(cls, results: list[WebSearchResult]) -> "WebSearchResponse":
        return cls(results=[WebSearchResultResponse.from_domain(result) for result in results])


class ImportWebSearchResultRequest(BaseModel):
    url: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
