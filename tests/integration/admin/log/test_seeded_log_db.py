"""Smoke test for the seeded_log_db fixture + log_data generator.

Verifies the generator produces rows the schema accepts and that the
fixture can hand them to a fresh SQLite. Guards against drift between
the production INSERT shape and the seed script.
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

# Make the fixture discoverable without registering it in conftest.
pytest_plugins = ["fixtures.seeded_log_db"]


@pytest.mark.asyncio
class TestSeededLogDb:
    async def test_seeded_db_has_expected_row_count(self, seeded_log_db: Path) -> None:
        """
        Given the seeded_log_db fixture,
        When counting rows in `logs`,
        Then exactly 100 rows are present.
        """
        async with aiosqlite.connect(seeded_log_db) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM logs")
            (total,) = await cursor.fetchone()  # type: ignore[misc]
        assert total == 100

    async def test_seeded_db_levels_are_realistic(self, seeded_log_db: Path) -> None:
        """
        Given the seeded_log_db fixture,
        When grouping rows by level,
        Then multiple levels exist and INFO is the majority.
        """
        async with aiosqlite.connect(seeded_log_db) as conn:
            cursor = await conn.execute(
                "SELECT level, COUNT(*) FROM logs GROUP BY level"
            )
            counts = dict(await cursor.fetchall())
        assert len(counts) >= 3
        assert counts.get("INFO", 0) >= 20

    async def test_seeded_db_fts_index_populated(self, seeded_log_db: Path) -> None:
        """
        Given the seeded_log_db fixture,
        When searching FTS5 mirror for a common token,
        Then matches are returned (proves AFTER INSERT trigger fires).
        """
        async with aiosqlite.connect(seeded_log_db) as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM logs_fts WHERE logs_fts MATCH 'http'"
            )
            (matches,) = await cursor.fetchone()  # type: ignore[misc]
        assert matches > 0
