from dataclasses import dataclass

from ...domain import ApiKeyRecord
from ..interfaces import IApiKeyRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class ListApiKeysUC:
    _repo: IApiKeyRepo

    async def __call__(self) -> list[ApiKeyRecord]:
        return await self._repo.list_active()
