from dataclasses import dataclass
from uuid import UUID

from shared.domain.auth import Principal, Role

from ...app import (
    AuthenticateUc,
    GenerateApiKeyUC,
    IssueTokensUC,
    ListApiKeysUC,
    RefreshTokensUC,
    RevokeApiKeyUC,
    RevokeTokenUC,
)
from ...domain import ApiKeyRecord, TokenPair


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
    _generate_api_key_uc: GenerateApiKeyUC
    _list_api_keys_uc: ListApiKeysUC
    _revoke_api_key_uc: RevokeApiKeyUC

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

    async def generate_api_key(self, *, name: str) -> tuple[UUID, str]:
        """Mint a new ADMIN API key. Returns (id, plaintext); the plaintext is
        shown ONCE and never recoverable (only its hash is stored)."""
        return await self._generate_api_key_uc(name=name, role=Role.ADMIN)

    async def list_api_keys(self) -> list[ApiKeyRecord]:
        """List active API keys (id, name, role, created_at). Never the secret."""
        return await self._list_api_keys_uc()

    async def revoke_api_key(self, api_key_id: UUID) -> None:
        """Soft-delete (revoke) an API key. Raises ApiKeyNotFound (404) if no
        active key with that id exists."""
        await self._revoke_api_key_uc(api_key_id)
