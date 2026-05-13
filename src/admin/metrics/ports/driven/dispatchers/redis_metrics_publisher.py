"""Per-worker metrics snapshot publisher (one Valkey hash per worker).

Hash key: `<prefix><role>:<host>:<pid>`. Rewritten in a HSET + EXPIRE
pipeline so a single round trip covers both. TTL > publish_interval
keeps live workers visible between ticks; dead workers vanish within
one TTL. Failures are swallowed — observability never crashes callers.
"""

import contextlib
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from ....domain import WorkerIdVo

_log = structlog.get_logger(__name__)


class IRedisClient(Protocol):
    def pipeline(self, transaction: bool = False) -> Any: ...

    async def aclose(self) -> None: ...


@dataclass(slots=True, kw_only=True)
class RedisMetricsPublisher:
    _redis: IRedisClient
    _key_prefix: str
    _key_ttl_s: int

    async def publish(
        self,
        worker_id: WorkerIdVo,
        role: str,
        fields: dict[str, str],
    ) -> None:
        key = f"{self._key_prefix}{role}:{worker_id}"
        # Inject identity fields so a Collector can rebuild the worker
        # without re-parsing the key.
        full = {**fields, "role": role, "worker_id": str(worker_id)}
        try:
            pipe = self._redis.pipeline(transaction=False)
            pipe.hset(key, mapping=full)
            pipe.expire(key, self._key_ttl_s)
            await pipe.execute()
        except Exception as exc:
            _log.warning(
                "metrics publish failed",
                role=role,
                worker_id=str(worker_id),
                error_type=type(exc).__name__,
            )

    async def aclose(self) -> None:
        with contextlib.suppress(Exception):
            await self._redis.aclose()
