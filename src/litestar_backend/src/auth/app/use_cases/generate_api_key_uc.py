from dataclasses import dataclass
from uuid import UUID

from shared.domain.auth import Role

from ...domain import generate_api_key
from ..interfaces import IApiKeyRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateApiKeyUC:
    _repo: IApiKeyRepo

    async def __call__(self, *, name: str, role: Role) -> tuple[UUID, str]:
        generated = generate_api_key()
        api_key_id = await self._repo.create(key_hash=generated.key_hash, name=name, role=role)
        return api_key_id, generated.plaintext
