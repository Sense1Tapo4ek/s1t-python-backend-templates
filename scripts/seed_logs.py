"""Seed admin_logs.db with realistic mock entries for demo / manual UI exploration.

Reads `LOG_DIR` (or falls back to `VOLUME_PATH/logs`) from the env the
app uses, runs migrations if the schema is missing, then bulk-inserts
N entries spanning the last `--minutes`. Reuses the same generator the
test suite uses (`tests/fixtures/log_data.py`).

Usage:
    uv run python scripts/seed_logs.py --count 1000 --minutes 120
    uv run python scripts/seed_logs.py --reset       # purge first
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import aiosqlite
from yoyo import get_backend, read_migrations  # type: ignore[import-untyped]

# Repo path setup — script lives at scripts/seed_logs.py.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "tests"))

from admin.log.config import AdminLogConfig  # noqa: E402
from fixtures.log_data import generate_log_rows  # noqa: E402

_INSERT_SQL = (
    "INSERT INTO logs ("
    "timestamp, level, logger, event, pathname, lineno, func_name, "
    "trace_id, span_id, raw_json"
    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def _apply_migrations(db_path: Path, migrations_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backend = get_backend(f"sqlite:///{db_path}")
    migrations = read_migrations(str(migrations_path))
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))


async def _seed(db_path: Path, *, count: int, minutes: int, reset: bool) -> int:
    async with aiosqlite.connect(db_path) as conn:
        if reset:
            await conn.execute("DELETE FROM logs")
        rows = generate_log_rows(count=count, span_minutes=minutes)
        await conn.executemany(_INSERT_SQL, rows)
        await conn.commit()
        cursor = await conn.execute("SELECT COUNT(*) FROM logs")
        (total,) = await cursor.fetchone()  # type: ignore[misc]
        return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=500, help="rows to insert (default 500)")
    parser.add_argument("--minutes", type=int, default=60, help="span back from now (default 60)")
    parser.add_argument("--reset", action="store_true", help="DELETE FROM logs first")
    args = parser.parse_args()

    cfg = AdminLogConfig()
    db_path = cfg.log_db_path
    print(f"seeding {db_path}")
    _apply_migrations(db_path, cfg.log_migrations_path)
    total = asyncio.run(_seed(db_path, count=args.count, minutes=args.minutes, reset=args.reset))
    print(f"inserted {args.count} rows; total now {total}")


if __name__ == "__main__":
    main()
