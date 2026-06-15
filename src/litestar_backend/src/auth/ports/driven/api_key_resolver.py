from dataclasses import dataclass

from shared.domain.auth import Principal

from ...app import IApiKeyRepo
from ...domain import API_KEY_PREFIX, hash_api_key


@dataclass(frozen=True, slots=True, kw_only=True)
class ApiKeyResolver:
    _repo: IApiKeyRepo

    async def resolve(self, token: str) -> Principal | None:
        # Shape gate: only ak_-prefixed tokens are API keys. JWTs and the static
        # admin token never reach the database lookup.
        if not token.startswith(API_KEY_PREFIX):
            return None
        record = await self._repo.find_active_by_hash(hash_api_key(token))
        if record is None:
            return None
        return Principal(role=record.role, token_id=record.id.hex[:8])
