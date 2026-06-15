from dataclasses import dataclass

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from shared.generics.errors import PortError


def _key(jti: str) -> str:
    return f"denylist:{jti}"


@dataclass(slots=True, kw_only=True)
class ValkeyDenylist:
    _valkey: aioredis.Redis

    async def add(self, jti: str, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        try:
            await self._valkey.set(_key(jti), "1", ex=ttl_seconds)
        except RedisError as exc:
            raise PortError(f"denylist add failed for {jti}: {exc}") from exc

    async def contains(self, jti: str) -> bool:
        try:
            return await self._valkey.exists(_key(jti)) == 1
        except RedisError as exc:
            raise PortError(f"denylist check failed for {jti}: {exc}") from exc
