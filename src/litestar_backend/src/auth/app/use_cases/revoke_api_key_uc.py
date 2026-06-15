from dataclasses import dataclass
from uuid import UUID

from ..errors import ApiKeyNotFound
from ..interfaces import IApiKeyRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class RevokeApiKeyUC:
    _repo: IApiKeyRepo

    async def __call__(self, api_key_id: UUID) -> None:
        if not await self._repo.soft_delete(api_key_id):
            raise ApiKeyNotFound(api_key_id)
