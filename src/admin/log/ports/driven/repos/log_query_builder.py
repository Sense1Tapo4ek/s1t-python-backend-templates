"""SQL builder for SQLiteLogRepo.

Pure module: takes a domain LogFilterVo + pagination args, returns a
parameterized SQL string and the bound params tuple.

Invariants on `LogFilterVo` fields (level vocabulary, kv key shape,
non-empty glob prefix) are enforced by `LogFilterVo.__post_init__` —
this builder trusts the VO and does no re-validation. SQL injection
is prevented by binding every dynamic value as a parameter (including
the json_extract path).
"""

import re
from dataclasses import dataclass

from ....domain import InvalidLogFilterError, LogFilterVo
from ....domain.dsl_constants import LEVEL_RANK


# Generated from the single LEVEL_RANK source of truth in domain.
def _build_rank_sql() -> str:
    whens = " ".join(f"WHEN '{level}' THEN {rank}" for level, rank in LEVEL_RANK.items())
    return f"CASE level {whens} ELSE 0 END"


_LEVEL_RANK_SQL = _build_rank_sql()


@dataclass(frozen=True, slots=True, kw_only=True)
class Query:
    sql: str
    params: tuple[int | str, ...]


def build_select(
    filter_vo: LogFilterVo | None,
    *,
    order: str = "DESC",
    limit: int | None = None,
    max_limit: int | None = None,
    before_cursor: int | None = None,
    after_cursor: int | None = None,
) -> Query:
    if order not in ("ASC", "DESC"):
        raise ValueError(f"order must be ASC or DESC, got {order!r}")
    if limit is not None and max_limit is not None and limit > max_limit:
        # Domain error so the global handler returns a 4xx rather than 500.
        raise InvalidLogFilterError(
            "limit",
            f"requested {limit} exceeds max {max_limit}",
        )

    conditions: list[str] = []
    params: list[int | str] = []
    needs_fts_join = False

    if filter_vo is not None:
        # min_level via numeric rank. VO guarantees the level is in vocabulary,
        # so the lookup is safe; KeyError here would be a programming bug.
        if filter_vo.min_level:
            conditions.append(f"{_LEVEL_RANK_SQL} >= ?")
            params.append(LEVEL_RANK[filter_vo.min_level.upper()])

        if filter_vo.levels:
            placeholders = ", ".join("?" * len(filter_vo.levels))
            conditions.append(f"level IN ({placeholders})")
            params.extend(lvl.upper() for lvl in filter_vo.levels)

        # loggers: each pattern becomes exact or glob; OR-joined.
        # VO guarantees glob patterns have a non-empty prefix.
        if filter_vo.loggers:
            logger_clauses: list[str] = []
            for pattern in filter_vo.loggers:
                if pattern.endswith(".*"):
                    prefix = pattern[:-2]
                    logger_clauses.append("logger LIKE ? || '.%'")
                    params.append(prefix)
                else:
                    logger_clauses.append("logger = ?")
                    params.append(pattern)
            conditions.append("(" + " OR ".join(logger_clauses) + ")")

        if filter_vo.trace_id:
            conditions.append("trace_id = ?")
            params.append(filter_vo.trace_id)

        # kv filters via json_extract. VO guarantees kv keys match the
        # safe regex; the path is bound as a parameter regardless.
        if filter_vo.kv_filters:
            for key, value in filter_vo.kv_filters:
                conditions.append("json_extract(raw_json, ?) = ?")
                params.append(f"$.{key}")
                params.append(value)

        if filter_vo.time_from is not None:
            conditions.append("timestamp >= ?")
            params.append(filter_vo.time_from.isoformat())
        if filter_vo.time_to is not None:
            conditions.append("timestamp <= ?")
            params.append(filter_vo.time_to.isoformat())

        if filter_vo.fts_phrase:
            conditions.append("logs_fts MATCH ?")
            params.append(_escape_fts5(filter_vo.fts_phrase))
            needs_fts_join = True

    if before_cursor is not None:
        conditions.append("id < ?")
        params.append(before_cursor)
    if after_cursor is not None:
        conditions.append("id > ?")
        params.append(after_cursor)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_clause = f"ORDER BY id {order}"
    limit_clause = ""
    if limit is not None:
        if limit < 0:
            raise ValueError(f"limit must be >= 0, got {limit}")
        limit_clause = "LIMIT ?"
        params.append(limit)

    if needs_fts_join:
        sql = (
            f"SELECT logs.* FROM logs "
            f"JOIN logs_fts ON logs.id = logs_fts.rowid "
            f"{where_clause} {order_clause} {limit_clause}"
        )
    else:
        sql = f"SELECT * FROM logs {where_clause} {order_clause} {limit_clause}"

    return Query(sql=_collapse_ws(sql), params=tuple(params))


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _escape_fts5(s: str) -> str:
    """Escape an arbitrary string into an FTS5 phrase literal.

    Doubles every embedded quote, then wraps the whole string in surrounding
    quotes so FTS5 treats it as one literal phrase — neutralising column
    filters, boolean operators, prefix `*`, etc.
    """
    return '"' + s.replace('"', '""') + '"'
