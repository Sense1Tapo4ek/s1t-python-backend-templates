"""Integration tests for SQLiteLogRepo against a real migrated sqlite db."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite
import orjson
import pytest
import pytest_asyncio
from yoyo import get_backend, read_migrations

from admin.log.config import YOYO_MIGRATION_TABLE
from admin.log.domain import LogFilterVo
from admin.log.ports.driven.repos import SQLiteLogRepo
from shared.adapters.driven.db import SQLiteConnection

_REPO_ROOT = Path(__file__).resolve().parents[4]
_MIGRATIONS = _REPO_ROOT / "migrations" / "admin_log"


def _migrate(db_path: Path) -> None:
    backend = get_backend(
        f"sqlite:///{db_path}",
        migration_table=YOYO_MIGRATION_TABLE,
    )
    with backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(read_migrations(str(_MIGRATIONS))))


async def _seed(conn: aiosqlite.Connection, rows: list[dict]) -> None:
    sql = (
        "INSERT INTO logs ("
        "timestamp, level, logger, event, pathname, lineno, func_name, "
        "trace_id, span_id, raw_json"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    payloads = [
        (
            r.get("timestamp"),
            r.get("level"),
            r.get("logger"),
            r.get("event"),
            r.get("pathname"),
            r.get("lineno"),
            r.get("func_name"),
            r.get("trace_id"),
            r.get("span_id"),
            orjson.dumps(r).decode(),
        )
        for r in rows
    ]
    await conn.executemany(sql, payloads)
    await conn.commit()


@pytest_asyncio.fixture
async def repo(tmp_path: Path):
    db = tmp_path / "logs.db"
    _migrate(db)
    conn = SQLiteConnection(_db_path=db)
    await conn.open()
    try:
        yield SQLiteLogRepo(_connection=conn), conn
    finally:
        await conn.close()


_BASE_TS = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def _row(idx: int, **overrides) -> dict:
    base = dict(
        timestamp=(_BASE_TS + timedelta(seconds=idx)).isoformat(),
        level="INFO",
        logger="ordering.app.create_uc",
        event=f"event {idx}",
        pathname="/src/x.py",
        lineno=10,
        func_name="run",
        trace_id=None,
        span_id=None,
        user_id="u_default",
    )
    base.update(overrides)
    return base


@pytest.mark.asyncio
class TestTailWithFilters:
    async def test_tail_returns_latest_n_in_chronological_order(self, repo) -> None:
        sut, conn = repo
        await _seed(conn.conn, [_row(i) for i in range(5)])

        entries, cursor, has_more = await sut.tail(size=3)

        assert [e.event for e in entries] == ["event 2", "event 3", "event 4"]
        assert cursor is not None
        assert cursor == entries[0].id
        assert has_more is True

    async def test_min_level_uses_rank(self, repo) -> None:
        """level:WARN+ should match WARN/ERROR/CRITICAL but not INFO."""
        sut, conn = repo
        await _seed(conn.conn, [
            _row(0, level="DEBUG"),
            _row(1, level="INFO"),
            _row(2, level="WARN"),
            _row(3, level="ERROR"),
            _row(4, level="CRITICAL"),
        ])

        entries, _, _ = await sut.tail(size=10, filter_vo=LogFilterVo(min_level="WARN"))

        assert sorted(e.level for e in entries) == ["CRITICAL", "ERROR", "WARN"]

    async def test_logger_glob_match(self, repo) -> None:
        """ordering.* matches ordering.x.y but not orderingX."""
        sut, conn = repo
        await _seed(conn.conn, [
            _row(0, logger="ordering.app"),
            _row(1, logger="ordering.app.create_uc"),
            _row(2, logger="orderingX.fake"),
            _row(3, logger="auth.login"),
        ])

        entries, _, _ = await sut.tail(
            size=10,
            filter_vo=LogFilterVo(loggers=("ordering.*",)),
        )

        loggers = sorted(e.logger for e in entries)
        assert loggers == ["ordering.app", "ordering.app.create_uc"]

    async def test_logger_exact_match(self, repo) -> None:
        sut, conn = repo
        await _seed(conn.conn, [
            _row(0, logger="auth"),
            _row(1, logger="auth.login"),
        ])

        entries, _, _ = await sut.tail(
            size=10,
            filter_vo=LogFilterVo(loggers=("auth",)),
        )

        assert [e.logger for e in entries] == ["auth"]

    async def test_kv_filter_via_json_extract(self, repo) -> None:
        sut, conn = repo
        await _seed(conn.conn, [
            _row(0, user_id="u1"),
            _row(1, user_id="u2"),
            _row(2, user_id="u1"),
        ])

        entries, _, _ = await sut.tail(
            size=10,
            filter_vo=LogFilterVo(kv_filters=(("user_id", "u1"),)),
        )

        assert len(entries) == 2
        assert all('"u1"' in e.raw_json for e in entries)

    async def test_trace_id_filter(self, repo) -> None:
        sut, conn = repo
        await _seed(conn.conn, [
            _row(0, trace_id="abc1234567890def"),
            _row(1, trace_id="ffff111122223333"),
            _row(2, trace_id="abc1234567890def"),
        ])

        entries, _, _ = await sut.tail(
            size=10,
            filter_vo=LogFilterVo(trace_id="abc1234567890def"),
        )

        assert len(entries) == 2
        assert all(e.trace_id == "abc1234567890def" for e in entries)

    async def test_time_range_filter(self, repo) -> None:
        sut, conn = repo
        await _seed(conn.conn, [_row(i) for i in range(5)])  # 12:00:00 .. 12:00:04

        entries, _, _ = await sut.tail(
            size=10,
            filter_vo=LogFilterVo(
                time_from=_BASE_TS + timedelta(seconds=2),
                time_to=_BASE_TS + timedelta(seconds=3),
            ),
        )

        assert sorted(e.event for e in entries) == ["event 2", "event 3"]

    async def test_text_search_via_fts(self, repo) -> None:
        """FTS5 trigram tokenizer matches substrings inside raw_json."""
        sut, conn = repo
        await _seed(conn.conn, [
            _row(0, event="payment failed"),
            _row(1, event="payment ok"),
            _row(2, event="other"),
        ])

        entries, _, _ = await sut.tail(
            size=10,
            filter_vo=LogFilterVo(fts_phrase="payment"),
        )

        # FTS5 trigram tokenizer matches the token "payment" inside raw_json
        assert len(entries) >= 2
        events = {e.event for e in entries}
        assert "payment failed" in events
        assert "payment ok" in events

    async def test_combined_filters_intersected(self, repo) -> None:
        sut, conn = repo
        await _seed(conn.conn, [
            _row(0, level="WARN", logger="ordering.app", user_id="u1"),
            _row(1, level="INFO", logger="ordering.app", user_id="u1"),
            _row(2, level="WARN", logger="auth", user_id="u1"),
            _row(3, level="WARN", logger="ordering.app", user_id="u2"),
        ])

        entries, _, _ = await sut.tail(
            size=10,
            filter_vo=LogFilterVo(
                min_level="WARN",
                loggers=("ordering.*",),
                kv_filters=(("user_id", "u1"),),
            ),
        )

        assert len(entries) == 1
        assert '"u1"' in entries[0].raw_json
        assert entries[0].level == "WARN"


@pytest.mark.asyncio
class TestTraceColumns:
    async def test_row_to_ent_maps_trace_columns(self, repo) -> None:
        sut, conn = repo
        await _seed(conn.conn, [
            _row(0, trace_id="abc1234567890def", span_id="01234567"),
        ])

        entries, _, _ = await sut.tail(size=1)

        assert entries[0].trace_id == "abc1234567890def"
        assert entries[0].span_id == "01234567"

    async def test_null_trace_columns_are_none(self, repo) -> None:
        sut, conn = repo
        await _seed(conn.conn, [_row(0)])

        entries, _, _ = await sut.tail(size=1)

        assert entries[0].trace_id is None
        assert entries[0].span_id is None
