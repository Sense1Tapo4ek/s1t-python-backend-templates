"""Pytest fixture that creates a temp admin_logs.db populated with mock rows.

Reuses `tests/fixtures/log_data.py` so the rows match what
`scripts/seed_logs.py` writes into the demo container.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite
import pytest_asyncio
from yoyo import get_backend, read_migrations  # type: ignore[import-untyped]

from fixtures.log_data import generate_log_rows

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MIGRATIONS_PATH = _PROJECT_ROOT / "migrations" / "admin_log"

_INSERT_SQL = (
    "INSERT INTO logs ("
    "timestamp, level, logger, event, pathname, lineno, func_name, "
    "trace_id, span_id, raw_json"
    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def _apply_migrations(db_path: Path) -> None:
    backend = get_backend(f"sqlite:///{db_path}")
    migrations = read_migrations(str(_MIGRATIONS_PATH))
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))


@pytest_asyncio.fixture
async def seeded_log_db(tmp_path: Path) -> AsyncIterator[Path]:
    """Yield a path to a SQLite file pre-loaded with 100 mock log rows."""
    db_path = tmp_path / "admin_logs.db"
    _apply_migrations(db_path)
    rows = generate_log_rows(count=100, span_minutes=30)
    async with aiosqlite.connect(db_path) as conn:
        await conn.executemany(_INSERT_SQL, rows)
        await conn.commit()
    yield db_path
