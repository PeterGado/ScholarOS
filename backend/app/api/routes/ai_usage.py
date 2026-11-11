from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel

from app.ai.usage_snapshot import AiUsageSnapshot, GetAiUsageSnapshotUseCase
from app.api.exception_handlers import ErrorResponse
from app.core.dependencies import get_ai_usage_snapshot_use_case, get_current_user_id
from app.core.rate_limit import limiter

router = APIRouter(prefix="/ai", tags=["ai"])


class AiUsageResponse(BaseModel):
    """AI usage over the rolling window the daily cap is enforced against. `remaining_tokens`
    is null when no cap is configured (unlimited), never 0 - a client that renders "0 left"
    for an unlimited account would be showing the exact opposite of the truth.
    """

    used_tokens: int
    daily_token_cap: int | None
    remaining_tokens: int | None
    window_hours: float

    @classmethod
    def from_snapshot(cls, snapshot: AiUsageSnapshot) -> "AiUsageResponse":
        return cls(
            used_tokens=snapshot.used_tokens,
            daily_token_cap=snapshot.daily_token_cap,
            remaining_tokens=snapshot.remaining_tokens,
            window_hours=snapshot.window_hours,
        )


@router.get(
    "/usage",
    response_model=AiUsageResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Missing, malformed, unknown, or ended session."},
        429: {"model": ErrorResponse, "description": "Too many usage checks from this client."},
    },
)
# 60/minute: this is meant to be polled by a sidebar/usage widget, so a tight per-minute cap
# would break normal polling while still bounding a runaway client - well below every other
# AI-adjacent route's own limit, since this one never calls a provider.
@limiter.limit("60/minute")
def get_ai_usage(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    use_case: GetAiUsageSnapshotUseCase = Depends(get_ai_usage_snapshot_use_case),
) -> AiUsageResponse:
    """The caller's own AI usage and remaining budget for the current window. Scoped to the
    authenticated user - there is no user_id parameter, so one account can never read
    another's usage (the same "identity comes only from the session" rule as every other
    route). No business logic here: the window sum and cap comparison live in
    GetAiUsageSnapshotUseCase.
    """
    return AiUsageResponse.from_snapshot(use_case.execute(user_id=user_id))
