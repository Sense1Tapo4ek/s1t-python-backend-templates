import asyncio

from yoyo import get_backend, read_migrations

_TABLE = "_yoyo_migration"


def _apply_sync(yoyo_url: str, migrations_dir: str) -> None:
    backend = get_backend(yoyo_url, migration_table=_TABLE)
    migrations = read_migrations(migrations_dir)
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))


async def run_migrations(yoyo_url: str, migrations_dir: str) -> None:
    # yoyo's psycopg3 backend is sync; run it off the event loop. Each context
    # passes its own migrations_dir, so one runner serves every asyncpg context.
    await asyncio.to_thread(_apply_sync, yoyo_url, migrations_dir)
