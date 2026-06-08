from dataclasses import dataclass
from uuid import UUID

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from shared.generics.errors import PortError

from ...app import IJoinStore
from ...domain import JobKind


def _key(video_id: UUID) -> str:
    return f"join:{video_id}"


@dataclass(slots=True, kw_only=True)
class ValkeyJoinStore(IJoinStore):
    _valkey: aioredis.Redis
    _ttl_seconds: int

    async def add(self, video_id: UUID, kind: JobKind) -> int:
        key = _key(video_id)
        try:
            async with self._valkey.pipeline(transaction=True) as pipe:
                pipe.sadd(key, kind.value)
                # reset TTL on each completion so a slow final job cannot let the join expire mid-flight
                pipe.expire(key, self._ttl_seconds)
                pipe.scard(key)
                results = await pipe.execute()
            return int(results[-1])
        except RedisError as exc:
            raise PortError(f"join add failed for {video_id}: {exc}") from exc

    async def clear(self, video_id: UUID) -> None:
        try:
            await self._valkey.delete(_key(video_id))
        except RedisError as exc:
            raise PortError(f"join clear failed for {video_id}: {exc}") from exc
