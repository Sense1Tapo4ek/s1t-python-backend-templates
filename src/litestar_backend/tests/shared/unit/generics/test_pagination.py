import base64
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from shared.generics.pagination import decode_cursor, encode_cursor


def _token(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).decode()


def test_round_trip() -> None:
    ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    vid = uuid4()
    assert decode_cursor(encode_cursor(ts, vid)) == (ts, vid)


@pytest.mark.parametrize(
    "bad",
    [
        "",  # empty
        "not-base64-!!",  # invalid base64
        _token("foo"),  # decodes, but no '|' separator
        _token("notadate|00000000-0000-0000-0000-000000000001"),  # bad datetime
        _token("2026-01-02T03:04:05+00:00|not-a-uuid"),  # bad uuid
    ],
)
def test_malformed_raises_value_error(bad: str) -> None:
    with pytest.raises(ValueError):
        decode_cursor(bad)
