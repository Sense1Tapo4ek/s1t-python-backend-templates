"""Realistic-shaped log entries for tests and demo seeding.

Single source of truth used by both pytest fixtures and the
`scripts/seed_logs.py` CLI. Rows are produced in chronological order so
the UI's "newest-first" listing matches reverse-iteration order.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

# 10-row insert tuple matching `_INSERT_SQL` in
# admin/log/adapters/driven/workers/log_sink_worker.py.
LogRow = tuple[
    str,       # timestamp
    str,       # level
    str,       # logger
    str,       # event
    str,       # pathname
    int,       # lineno
    str,       # func_name
    str | None,  # trace_id
    str | None,  # span_id
    str,       # raw_json
]


_LEVELS_WEIGHTED: list[tuple[str, int]] = [
    ("DEBUG",    20),
    ("INFO",     55),
    ("WARNING",  15),
    ("ERROR",     8),
    ("CRITICAL",  2),
]

_LOGGERS = [
    "root.api",
    "auth.middleware",
    "admin.log.api",
    "admin.log.worker",
    "admin.metrics.publisher",
    "admin.metrics.collector",
    "shared.event_bus",
    "shared.access_log",
    "snitchbot.client",
]

_HTTP_ROUTES = [
    ("/health", 200),
    ("/admin", 200),
    ("/admin/login", 302),
    ("/admin/logs/", 200),
    ("/admin/metrics/", 200),
    ("/metrics", 200),
    ("/api/v1/admin/logs/", 200),
    ("/api/v1/admin/logs/stream", 200),
    ("/api/v1/admin/logs/", 401),
    ("/api/v1/admin/logs/export", 200),
    ("/api/v1/admin/logs/", 400),
    ("/admin/metrics/api", 200),
    ("/admin/metrics/no-such", 404),
]

_EVENT_TEMPLATES: list[tuple[str, str, dict[str, Any]]] = [
    ("INFO",     "http request",          {"method": "GET", "duration_ms": 0}),
    ("INFO",     "http request",          {"method": "POST", "duration_ms": 0}),
    ("INFO",     "user authenticated",    {"role": "admin", "via": "cookie"}),
    ("WARNING",  "auth failed",           {"reason": "bad token"}),
    ("INFO",     "logs page served",      {"entry_count": 200, "has_more": True}),
    ("INFO",     "logs older served",     {"entry_count": 200, "has_more": True}),
    ("INFO",     "logs stream opened",    {"q": None, "min_level": None}),
    ("INFO",     "logs stream closed",    {"q": None, "min_level": None}),
    ("INFO",     "export started",        {"format": "ndjson"}),
    ("WARNING",  "dsl rejected",          {"position": 14, "reason": "unknown token"}),
    ("WARNING",  "log filter rejected",   {"field": "level", "reason": "unsupported"}),
    ("INFO",     "metrics published",     {"role": "api"}),
    ("INFO",     "metrics published",     {"role": "sink"}),
    ("WARNING",  "queue depth high",      {"depth": 4321}),
    ("ERROR",    "db query slow",         {"duration_ms": 2400}),
    ("ERROR",    "valkey unreachable",    {"endpoint": "redis://valkey:6379/0"}),
    ("CRITICAL", "sink crashed",          {"reason": "oom"}),
    ("DEBUG",    "config loaded",         {"keys": ["LOG_BATCH_SIZE", "AUTH_ADMIN_TOKEN"]}),
    ("DEBUG",    "event bus tick",        {"queued": 12}),
    ("INFO",     "lifespan started",      {}),
    ("INFO",     "lifespan stopped",      {}),
    ("WARNING",  "request slow",          {"duration_ms": 1820}),
    ("ERROR",    "handler raised",        {"exc_type": "PortError"}),
]


def _weighted_level(rng: random.Random) -> str:
    pool = [lvl for lvl, weight in _LEVELS_WEIGHTED for _ in range(weight)]
    return rng.choice(pool)


def _format_ts(dt: datetime) -> str:
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000).isoformat()


def generate_log_rows(
    count: int = 500,
    *,
    span_minutes: int = 60,
    end: datetime | None = None,
    seed: int = 42,
) -> list[LogRow]:
    """Build `count` realistic log rows spanning `span_minutes` ending at `end`.

    Deterministic given `seed`. Returns rows in chronological order; the
    caller appends them to the DB and the existing autoincrement id keeps
    that order intact.
    """
    rng = random.Random(seed)
    end = (end or datetime.now(UTC)).replace(microsecond=0)
    span = timedelta(minutes=span_minutes)
    trace_pool = [uuid4().hex[:16] for _ in range(max(8, count // 25))]
    rows: list[LogRow] = []

    for i in range(count):
        # Place each row at a deterministic offset back from `end`.
        offset = span * (1 - i / max(1, count - 1))
        ts = end - offset
        trace_id = rng.choice(trace_pool) if rng.random() < 0.85 else None
        span_id = uuid4().hex[:16] if trace_id else None
        logger = rng.choice(_LOGGERS)

        if rng.random() < 0.45:
            route, status = rng.choice(_HTTP_ROUTES)
            level = "ERROR" if status >= 500 else ("WARNING" if status >= 400 else "INFO")
            event = "http request"
            extra: dict[str, Any] = {
                "method": rng.choice(["GET", "POST", "DELETE"]),
                "route": route,
                "status": status,
                "duration_ms": round(rng.gammavariate(2.0, 30.0), 1),
            }
        else:
            tpl_level, event, tpl_extra = rng.choice(_EVENT_TEMPLATES)
            level = tpl_level if rng.random() < 0.75 else _weighted_level(rng)
            extra = dict(tpl_extra)
            if "duration_ms" in extra and extra["duration_ms"] == 0:
                extra["duration_ms"] = round(rng.gammavariate(2.0, 30.0), 1)

        if level in {"ERROR", "CRITICAL"} and rng.random() < 0.5:
            extra["exception"] = {
                "type": rng.choice(["PortError", "ValueError", "RuntimeError", "TimeoutError"]),
                "message": "synthetic failure for demo data",
            }

        record: dict[str, Any] = {
            "timestamp": _format_ts(ts),
            "level": level,
            "logger": logger,
            "event": event,
            "trace_id": trace_id,
            "span_id": span_id,
            **extra,
        }
        rows.append((
            record["timestamp"],
            level,
            logger,
            event,
            f"src/{logger.replace('.', '/')}.py",
            rng.randint(20, 400),
            rng.choice(["_run", "__call__", "publish", "handle", "tick"]),
            trace_id,
            span_id,
            json.dumps(record, separators=(",", ":")),
        ))

    return rows
