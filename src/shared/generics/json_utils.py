from typing import Any

import orjson


def filter_raw_record(raw: str, reserved: frozenset[str]) -> dict[str, Any]:
    """Parse a raw structlog event JSON and drop reserved keys.

    Returns {} when:
    - `raw` is not valid JSON,
    - the parsed value is not an object (e.g. a bare string or list).

    The empty-dict sentinel keeps callers branch-free; serialization choices
    (compact separators, empty-string vs `"{}"`) stay at the call site
    because they encode display contracts (CSV column vs SSE payload), not
    parsing concerns.

    Uses orjson over stdlib json: ~5-10x faster on the API/export hot path
    where this runs once per record.
    """
    try:
        record = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return {}
    if not isinstance(record, dict):
        return {}
    return {k: v for k, v in record.items() if k not in reserved}
