from pydantic import BaseModel

from app.modules.knowledge.application.retrieval import SearchResult


class SearchResultEvidenceResponse(BaseModel):
    document_id: int
    document_title: str


class SearchResultResponse(BaseModel):
    """One ranked result. Deliberately excludes the embedding vector - it is a storage/
    retrieval implementation detail, never part of the public contract (mirrors
    `ResearchDocumentResponse` excluding `content_reference` for the same reason).
    """

    chunk_id: int
    content: str
    summary: str | None
    score: float
    evidence: list[SearchResultEvidenceResponse]

    @classmethod
    def from_domain(cls, result: SearchResult) -> "SearchResultResponse":
        return cls(
            chunk_id=result.chunk_id,
            content=result.content,
            summary=result.summary,
            score=result.score,
            evidence=[
                SearchResultEvidenceResponse(document_id=e.document_id, document_title=e.document_title)
                for e in result.evidence
            ],
        )


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]

    @classmethod
    def from_domain(cls, results: list[SearchResult]) -> "SearchResponse":
        return cls(results=[SearchResultResponse.from_domain(r) for r in results])
