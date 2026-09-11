from app.core.exceptions import ScholarOSError


class AgentDomainError(ScholarOSError):
    """Base class for Agent domain errors."""


class AgentAlreadyExistsForUserError(AgentDomainError):
    """Raised when a user who already owns an Agent attempts to create another one.

    One Agent per user is the MVP invariant (05_Constraints_and_Integrity.md invariant 15;
    ADR-009). Multiple Agents per user is a deferred, monetization-gated capability.
    """

    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} already owns an Agent (one Agent per user in the MVP).")
        self.user_id = user_id


class AgentNotFoundForUserError(AgentDomainError):
    """Raised when an authenticated user has no Agent yet (e.g. has never called
    POST /agents). Distinct from "Agent exists but has no knowledge yet" - Stage 8's search
    endpoint must not conflate the two (the API contract in Backend_Slice2_Implementation_
    Plan.md §9 already called for this distinction).
    """

    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} does not have an Agent yet.")
        self.user_id = user_id
