from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedIdentity:
    """The resolved identity of the caller of the current request. Boundary-internal -
    `get_current_user_id` unwraps this to the plain `user_id: int` every existing call site
    already expects (ADR-010: the dependency's signature and call sites are unchanged).
    """

    user_id: int
