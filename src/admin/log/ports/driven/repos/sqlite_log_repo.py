import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import aiosqlite

from shared.adapters.driven.db import SQLiteConnection

from ....app.interfaces import ILogPurger, ILogReader
from ....domain import LogEntryEnt, LogFilterVo, LogId
from .log_query_builder import build_select

# Fixed batch size for SSE catch-up polling. Internal value, not caller-
# controlled, so it bypasses `_max_limit`.
_STREAM_TAIL_BATCH = 50

# Chunk size for unbounded export streaming. Large enough to amortise
# query overhead; small enough to release the reader between chunks.
_STREAM_QUERY_CHUNK = 500


@dataclass(slots=True, kw_only=True)
class SQLiteLogRepo(ILogReader, ILogPurger):
    """ILogReader / ILogPurger over a single SQLite file with FTS5 trigram.

    Reads go through the connection's reader pool; the only writer is the
    sink worker. DSL → SQL translation lives in `log_query_builder`; this
    class owns row → entity mapping and the cursor protocol. `_max_limit`
    caps any single page to protect memory; callers must not bypass it.
    """

    _connection: SQLiteConnection
    _stream_poll_interval_s: float = 3.0
    _max_limit: int = 5000

    async def purge_all(self) -> int:
        async with self._connection.transaction() as db:
            cur = await db.execute("DELETE FROM logs")
            deleted = cur.rowcount or 0
        return deleted

    async def tail(
        self,
        size: int,
        filter_vo: LogFilterVo | None = None,
    ) -> tuple[list[LogEntryEnt], LogId | None, bool]:
        # Request size+1 so we can report has_more without a follow-up
        # COUNT query. The overflow row, if present, is dropped before
        # the result is returned to the caller.
        rows = await self._select_desc(
            filter_vo=filter_vo,
            limit=size + 1,
            before_cursor=None,
        )
        has_more = len(rows) > size
        if has_more:
            rows = rows[:size]
        entries = [_row_to_ent(row) for row in reversed(rows)]
        cursor = entries[0].id if entries else None
        return entries, cursor, has_more

    async def read_before(
        self,
        cursor: LogId,
        size: int,
        filter_vo: LogFilterVo | None = None,
    ) -> tuple[list[LogEntryEnt], LogId | None, bool]:
        rows = await self._select_desc(
            filter_vo=filter_vo,
            limit=size + 1,
            before_cursor=cursor,
        )
        has_more = len(rows) > size
        if has_more:
            rows = rows[:size]
        entries = [_row_to_ent(row) for row in reversed(rows)]
        next_cursor = entries[0].id if entries else None
        return entries, next_cursor, has_more

    async def _select_desc(
        self,
        *,
        filter_vo: LogFilterVo | None,
        limit: int,
        before_cursor: LogId | None,
    ) -> list[aiosqlite.Row]:
        query = build_select(
            filter_vo,
            order="DESC",
            limit=limit,
            max_limit=self._max_limit,
            before_cursor=before_cursor,
        )
        async with (
            self._connection.read() as db,
            db.execute(query.sql, query.params) as cursor_obj,
        ):
            return list(await cursor_obj.fetchall())

    async def stream_after(
        self,
        cursor: LogId | None = None,
        filter_vo: LogFilterVo | None = None,
    ) -> AsyncGenerator[LogEntryEnt, None]:
        if cursor is None:
            async with (
                self._connection.read() as db,
                db.execute("SELECT MAX(id) FROM logs") as cur,
            ):
                row = await cur.fetchone()
                # SELECT MAX(...) on an empty table returns one row with NULL,
                # not zero rows, so `row` is never None here.
                last_id = (row[0] if row is not None else None) or 0
        else:
            last_id = cursor

        while True:
            query = build_select(
                filter_vo,
                order="ASC",
                limit=_STREAM_TAIL_BATCH,
                after_cursor=last_id,
            )
            async with (
                self._connection.read() as db,
                db.execute(query.sql, query.params) as cursor_obj,
            ):
                rows = list(await cursor_obj.fetchall())

            if not rows:
                await asyncio.sleep(self._stream_poll_interval_s)
                continue

            for row in rows:
                entry = _row_to_ent(row)
                last_id = entry.id
                yield entry

    async def stream_query(
        self,
        filter_vo: LogFilterVo | None = None,
    ) -> AsyncGenerator[LogEntryEnt, None]:
        # Paginate by ascending id with LIMIT to release the reader between
        # chunks; otherwise a slow consumer (e.g. SSE export) would pin one
        # reader for the entire export and exhaust the pool.
        last_id = 0
        while True:
            query = build_select(
                filter_vo,
                order="ASC",
                limit=_STREAM_QUERY_CHUNK,
                after_cursor=last_id,
            )
            async with (
                self._connection.read() as db,
                db.execute(query.sql, query.params) as cursor_obj,
            ):
                rows = list(await cursor_obj.fetchall())

            if not rows:
                return
            for row in rows:
                entry = _row_to_ent(row)
                last_id = entry.id
                yield entry


def _row_to_ent(row: aiosqlite.Row) -> LogEntryEnt:
    return LogEntryEnt(
        id=LogId(row["id"]),
        timestamp=row["timestamp"],
        level=row["level"],
        logger=row["logger"],
        event=row["event"],
        pathname=row["pathname"],
        lineno=row["lineno"],
        func_name=row["func_name"],
        raw_json=row["raw_json"],
        trace_id=row["trace_id"],
        span_id=row["span_id"],
    )
