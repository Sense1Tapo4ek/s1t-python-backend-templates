from dataclasses import dataclass

from .role import Role


@dataclass(frozen=True, slots=True, kw_only=True)
class Principal:
    """Authenticated identity -- role-based, no user identity yet.

    `token_id` is a short hash of the bearer token, suitable for logging
    and request correlation. The raw token is NEVER stored on the Principal.
    `subject` is the JWT `sub` claim when the credential identifies a stored
    user (their UUID as a string); None for role-only credentials (static
    admin token, API keys, admin-minted pairs).
    """

    role: Role
    token_id: str
    subject: str | None = None
