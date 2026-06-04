import asyncpg


async def build_pool(dsn: str, *, schema: str, size: int) -> asyncpg.Pool:
    pool: asyncpg.Pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=size,
        server_settings={"search_path": schema},
    )
    return pool
