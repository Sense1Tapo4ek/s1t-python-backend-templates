from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, literal, tuple_


def keyset_older_than(
    ts_col: Any, id_col: Any, after: tuple[datetime, UUID]
) -> ColumnElement[bool]:
    """WHERE clause selecting rows strictly older than the (ts, id) position.

    Postgres compares row values lexicographically, so `< after` returns rows
    strictly "older" than the cursor with the id as the tie-breaker -- pair it
    with `ORDER BY ts DESC, id DESC` and a LIMIT for a stable keyset page.
    """
    return tuple_(ts_col, id_col) < tuple_(literal(after[0]), literal(after[1]))
