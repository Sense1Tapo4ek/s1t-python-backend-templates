import redis.asyncio as aioredis


def build_valkey(url: str) -> aioredis.Redis:
    return aioredis.from_url(url, decode_responses=True)
