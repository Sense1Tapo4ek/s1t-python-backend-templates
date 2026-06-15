from typing import Protocol

from ..domain import TokenType, VerifiedToken


class IJwtVerifier(Protocol):
    def verify(self, token: str, *, expected_type: TokenType | None = None) -> VerifiedToken | None:
        """Verify a JWT and project it to a VerifiedToken, or None.

        Checks signature, timing, issuer, and (when `expected_type` is given)
        the `type` claim. Returns None on any failure -- callers MUST treat
        None as "not a usable credential". Does NOT consult the denylist;
        revocation is the caller's concern.
        """
        ...
