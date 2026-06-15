from typing import Protocol


class IDenylist(Protocol):
    async def add(self, jti: str, *, ttl_seconds: int) -> None:
        """Record `jti` as revoked for `ttl_seconds`, then auto-expire.

        Idempotent: re-adding a live `jti` is harmless. A non-positive
        `ttl_seconds` is a no-op (the token has already expired, so the
        denylist need not outlive it).

        Raises:
            PortError: the Valkey backend is unreachable or rejected the write.
        """
        ...

    async def contains(self, jti: str) -> bool:
        """Return True iff `jti` is currently denylisted (revoked, not expired).

        Raises:
            PortError: the Valkey backend is unreachable or rejected the read.
        """
        ...
