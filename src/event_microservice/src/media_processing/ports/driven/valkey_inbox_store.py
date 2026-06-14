from dataclasses import dataclass
from uuid import UUID

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from shared.generics.errors import PortError

from ...app import IInboxStore


def _key(event_id: UUID) -> str:
    return f"inbox:{event_id}"


@dataclass(slots=True, kw_only=True)
class ValkeyInboxStore(IInboxStore):
    _valkey: aioredis.Redis
    _ttl_seconds: int

    async def seen(self, event_id: UUID) -> bool:
        try:
            return await self._valkey.exists(_key(event_id)) == 1
        except RedisError as exc:
            raise PortError(f"inbox seen check failed for {event_id}: {exc}") from exc

    async def mark_processed(self, event_id: UUID) -> None:
        try:
            await self._valkey.set(_key(event_id), "1", ex=self._ttl_seconds)
        except RedisError as exc:
            raise PortError(f"inbox mark failed for {event_id}: {exc}") from exc
