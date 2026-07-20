from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared.domain.auth import Principal, Role
from shared.generics.pagination import Page, encode_cursor

from ...app import (
    AuthenticateUc,
    DeactivateUserUC,
    GenerateApiKeyUC,
    IssueTokensUC,
    ListApiKeysUC,
    ListUsersUC,
    LoginUserUC,
    RefreshTokensUC,
    RegisterUserUC,
    RevokeApiKeyUC,
    RevokeTokenUC,
)
from ...domain import ApiKeyRecord, TokenPair
from .user_dto import UserResponse


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
    _register_uc: RegisterUserUC
    _login_uc: LoginUserUC
    _list_users_uc: ListUsersUC
    _deactivate_user_uc: DeactivateUserUC

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

    async def register(self, *, email: str, password: str) -> UserResponse:
        """Create a Role.USER account; stages `user_registered` atomically.

        Raises:
            EmailTakenError: an active account already uses this email (409).
            PortError: storage failure (503).
        """
        return UserResponse.of(await self._register_uc(email=email, password=password))

    async def login(self, *, email: str, password: str) -> TokenPair | None:
        """Verify credentials and mint a user-bound JWT pair.

        Returns None for ANY bad credential (unknown email, wrong password,
        deactivated account) -- the controller maps None to one uniform 401.

        Raises:
            JwtDisabledError: no signing secret configured (503).
            PortError: storage failure (503).
        """
        return await self._login_uc(email=email, password=password)

    async def list_users(
        self, after: tuple[datetime, UUID] | None, limit: int
    ) -> Page[UserResponse]:
        """Active users, newest-first keyset page; admin actor only.

        `after` is the decoded cursor (controller owns decoding + the 400);
        `next_cursor` is set only when the page is full.
        """
        users = await self._list_users_uc(after, limit)
        next_cursor = (
            encode_cursor(users[-1].created_at, users[-1].id) if len(users) == limit else None
        )
        return Page(items=[UserResponse.of(u) for u in users], next_cursor=next_cursor)

    async def deactivate_user(self, user_id: UUID) -> None:
        """Soft-delete a user: blocks login and refresh immediately; already
        issued access tokens live out their TTL. Raises UserNotFound (404)."""
        await self._deactivate_user_uc(user_id)
