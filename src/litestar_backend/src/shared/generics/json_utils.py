from typing import Any

import orjson


def filter_raw_record(raw: str, reserved: frozenset[str]) -> dict[str, Any]:
    """Parse a structlog event JSON; drop reserved keys; {} on non-object input.

    Empty-dict sentinel keeps callers branch-free. orjson chosen for
    ~5-10x speed on the per-record export hot path.
    """
    try:
        record = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return {}
    if not isinstance(record, dict):
        return {}
    return {k: v for k, v in record.items() if k not in reserved}
