import redis.asyncio as aioredis


def build_valkey_client(
    url: str,
    *,
    max_connections: int = 20,
    socket_timeout: float = 5.0,
) -> aioredis.Redis:
    # decode_responses=True so reads are str, consistent with the msgspec-first
    # wire convention; the connection pool is owned by the client and closed by
    # aclose().
    return aioredis.Redis.from_url(
        url,
        max_connections=max_connections,
        socket_timeout=socket_timeout,
        decode_responses=True,
    )
