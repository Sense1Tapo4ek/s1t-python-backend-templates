from typing import Any, Protocol


class IJwtCodec(Protocol):
    def encode(self, header: dict[str, Any], claims: dict[str, Any]) -> str | None:
        """Sign `claims` into a compact JWS string, or None if JWT is disabled.

        Datetime values in `claims` (iat/exp/nbf) are converted to integer
        timestamps. Returns None iff no signing key is configured.
        """
        ...

    def decode(self, token: str) -> dict[str, Any] | None:
        """Verify the signature and parse the claims, or None.

        Restricted to HS256 (alg-confusion / `none` attacks rejected). Returns
        None for a bad signature, a malformed token, or when JWT is disabled.
        Does NOT validate timing (exp/nbf) or claim values (iss/type/role) --
        those are the verifier's concern.
        """
        ...
