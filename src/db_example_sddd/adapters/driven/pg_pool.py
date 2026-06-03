import asyncpg


async def build_pool(dsn: str, *, schema: str, size: int) -> asyncpg.Pool:
    # search_path is a startup-packet parameter, so it survives pool connection
    # reset/recycle -- unqualified queries resolve in the context schema.
    pool: asyncpg.Pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=size,
        server_settings={"search_path": schema},
    )
    return pool


async def open_connection(dsn: str, *, schema: str) -> asyncpg.Connection:
    # Per-request variant: a fresh connection, no pooling -- preserves the
    # pooled-vs-per-request teaching contrast.
    return await asyncpg.connect(dsn, server_settings={"search_path": schema})
