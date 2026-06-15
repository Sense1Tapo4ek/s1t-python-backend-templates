from dataclasses import dataclass

from shared.domain.auth import Principal, Role

from ...app import AuthenticateUc, IssueTokensUC, RefreshTokensUC, RevokeTokenUC
from ...domain import TokenPair


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthFacade:
    """Driving port for the auth bounded context; serves the admin actor.

    Verifies credentials (static token or JWT) and mints/rotates/revokes JWT
    pairs. The middleware uses `authenticate`; the `/auth/*` controller uses
    the token methods.
    """

    _authenticate_uc: AuthenticateUc
    _issue_uc: IssueTokensUC
    _refresh_uc: RefreshTokensUC
    _revoke_uc: RevokeTokenUC

    async def authenticate(self, token: str) -> Principal | None:
        """Verify a bearer token (JWT or static admin) and return its Principal.

        Returns:
            Principal for a valid credential, or None for any invalid, empty,
            or unrecognised token.

        Raises:
            PortError: the JWT denylist (Valkey) is unreachable. The middleware
            catches this and fails closed (treats the request as anonymous).
        """
        return await self._authenticate_uc(token)

    def issue_tokens(self, *, role: Role) -> TokenPair:
        """Mint a fresh access+refresh pair for `role`.

        Raises:
            JwtDisabledError: no JWT signing secret is configured (maps to 503).
        """
        return self._issue_uc(role=role)

    async def refresh_tokens(self, refresh_token: str) -> TokenPair | None:
        """Rotate a refresh token: verify it, revoke its jti, return a new pair.

        Returns:
            A new TokenPair, or None if the refresh token is invalid, expired,
            or already rotated/revoked (the controller maps None to 401).
        """
        return await self._refresh_uc(refresh_token)

    async def revoke_token(self, token: str) -> None:
        """Best-effort revoke: denylist the token's jti for its remaining life.

        Idempotent: revoking an invalid or already-expired token is a no-op.
        """
        return await self._revoke_uc(token)
