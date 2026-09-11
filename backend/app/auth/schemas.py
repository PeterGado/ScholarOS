from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request body for POST /auth/login. Not yet wired to a route (Stage 5)."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Response body for POST /auth/login. Deliberately contains nothing but the token -
    no session_id, no timestamps, no internal fields (05_Constraints_and_Integrity.md §17).
    """

    access_token: str
    token_type: str = "bearer"
