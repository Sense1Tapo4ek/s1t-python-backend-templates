import time
from typing import Any

import structlog
from prometheus_client import Histogram
from sqlalchemy import event
from sqlalchemy.engine import Engine

_log = structlog.get_logger("postgres.query")

# Module-level so it registers once on import and survives repeated create_app()
# in tests (same pattern as videos_uploaded_total). Multiprocess-mode safe.
DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "SQL statement execution time, seconds.",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

# Statements at or above this are logged at WARNING. Tune per deployment.
SLOW_QUERY_S = 0.1


def _digest(statement: str) -> str:
    # Log the statement TEMPLATE (no bound param values -> no PII), whitespace
    # collapsed and truncated to keep log lines bounded.
    return " ".join(statement.split())[:120]


def attach_query_observability(sync_engine: Engine) -> None:
    """Attach query timing to a (sync) Core engine.

    For an AsyncEngine, pass `async_engine.sync_engine`. Idempotent per engine is
    NOT guaranteed -- call once per engine (build_engine does).
    """

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        context._query_start = time.perf_counter()

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        start = getattr(context, "_query_start", None)
        if start is None:
            return  # before_cursor_execute did not run -- no start, skip rather than record a bogus sample
        elapsed = time.perf_counter() - start
        DB_QUERY_DURATION.observe(elapsed)
        if elapsed >= SLOW_QUERY_S:
            _log.warning(
                "db query slow",
                duration_ms=round(elapsed * 1000, 2),
                statement=_digest(statement),
            )
