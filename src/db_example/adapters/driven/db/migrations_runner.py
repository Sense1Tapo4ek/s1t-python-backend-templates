import asyncio
from pathlib import Path

from yoyo import get_backend, read_migrations

_MIGRATIONS_DIR = "migrations/db_example"
_TABLE = "_yoyo_migration"


def _apply_sync(db_path: Path) -> None:
    backend = get_backend(f"sqlite:///{db_path}", migration_table=_TABLE)
    migrations = read_migrations(_MIGRATIONS_DIR)
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))


async def apply_migrations(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(_apply_sync, db_path)
