import asyncio

from yoyo import get_backend, read_migrations

from shared.generics.config import PROJECT_ROOT

_MIGRATIONS_DIR = str(PROJECT_ROOT / "migrations" / "db_example_sddd")
_TABLE = "_yoyo_migration"


def _apply_sync(yoyo_url: str) -> None:
    backend = get_backend(yoyo_url, migration_table=_TABLE)
    migrations = read_migrations(_MIGRATIONS_DIR)
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))


async def apply_migrations(yoyo_url: str) -> None:
    # yoyo + the postgresql+psycopg scheme -> PostgresqlPsycopgBackend (psycopg3).
    await asyncio.to_thread(_apply_sync, yoyo_url)
