from typing import Protocol

from shared.domain.auth import Role

from ...domain import TokenPair, TokenType, VerifiedToken


class IJwtService(Protocol):
    """Mint and verify JWTs (one cohesive service, implemented by JwtService)."""

    def issue_pair(self, *, role: Role, subject: str | None = None) -> TokenPair | None:
        """Mint a fresh access+refresh pair for `role`.

        `subject` becomes the `sub` claim when the pair belongs to a stored
        user (their UUID as a string); None mints a role-only pair with
        `sub == role.value`. Each token carries a unique `jti`. Returns None
        iff JWT is disabled (no signing secret configured) -- callers map
        that to a 503.
        """
        ...

    def verify(self, token: str, *, expected_type: TokenType | None = None) -> VerifiedToken | None:
        """Verify a JWT and project it to a VerifiedToken, or None.

        Checks signature, timing, issuer, and (when `expected_type` is given)
        the `type` claim. Returns None on any failure -- callers MUST treat
        None as "not a usable credential". Does NOT consult the denylist;
        revocation is the caller's concern.
        """
        ...
