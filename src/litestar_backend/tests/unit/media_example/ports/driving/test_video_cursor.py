from datetime import UTC, datetime
from uuid import uuid4

import pytest

from media_example.ports.driving.video_cursor import decode_cursor, encode_cursor


def test_round_trip() -> None:
    ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    vid = uuid4()
    assert decode_cursor(encode_cursor(ts, vid)) == (ts, vid)


@pytest.mark.parametrize("bad", ["", "not-base64-!!", "Zm9v"])  # "Zm9v" -> "foo", no '|'
def test_malformed_raises_value_error(bad: str) -> None:
    with pytest.raises(ValueError):
        decode_cursor(bad)
