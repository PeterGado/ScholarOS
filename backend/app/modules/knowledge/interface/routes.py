from fastapi import APIRouter, Depends, Query, Request, status

from app.api.exception_handlers import ErrorResponse
from app.core.dependencies import get_current_user_id, get_search_knowledge_use_case
from app.core.rate_limit import limiter
from app.modules.knowledge.application.retrieval import DEFAULT_TOP_K, MAX_TOP_K, SearchKnowledgeUseCase
from app.modules.knowledge.interface.schemas import SearchResponse

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        404: {"model": ErrorResponse, "description": "The authenticated user does not have an Agent yet."},
        422: {"model": ErrorResponse, "description": "Missing/empty query or out-of-range top_k."},
        429: {"model": ErrorResponse, "description": "Too many searches from this client, or the daily AI usage cap was reached."},
        502: {"model": ErrorResponse, "description": "The AI provider request failed."},
        503: {"model": ErrorResponse, "description": "The AI provider is not configured."},
    },
)
# 2026-09-21 security pass: found with no rate limit at all while mapping AI call sites for the
# usage-cap work - a synchronous per-request embedding call, same cost profile as the other
# AI-adjacent routes, which were all already rate-limited.
@limiter.limit("20/minute")
def search_knowledge(
    request: Request,
    q: str = Query(..., min_length=1, description="The search query text."),
    top_k: int = Query(DEFAULT_TOP_K, ge=1, le=MAX_TOP_K, description="Maximum number of results to return."),
    user_id: int = Depends(get_current_user_id),
    use_case: SearchKnowledgeUseCase = Depends(get_search_knowledge_use_case),
) -> SearchResponse:
    """Vector search over the caller's own Knowledge Chunks (Stage 8; 04_AI_Architecture.md
    §16). The authenticated identity resolves the caller's own Agent internally - the client
    never supplies an agent_id, so one agent can never retrieve another agent's knowledge.

    No business logic lives here: agent resolution, embedding, ranking, and evidence
    assembly all happen in SearchKnowledgeUseCase; exceptions are translated to HTTP
    responses by the handlers registered in app.api.exception_handlers.
    """
    results = use_case.execute(user_id=user_id, query=q, top_k=top_k)
    return SearchResponse.from_domain(results)
