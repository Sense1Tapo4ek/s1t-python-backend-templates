import base64
import binascii
from datetime import datetime
from uuid import UUID

import msgspec


class Page[T](msgspec.Struct, kw_only=True):
    """Keyset-pagination response envelope: one page + the cursor to the next.

    `next_cursor` is None on the final page; otherwise it encodes the keyset
    position of the last item and is opaque to clients.
    """

    items: list[T]
    next_cursor: str | None


def encode_cursor(ts: datetime, item_id: UUID) -> str:
    """Opaque, URL-safe token encoding the keyset position (timestamp, id)."""
    raw = f"{ts.isoformat()}|{item_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Inverse of encode_cursor. Raises ValueError on any malformed token.

    The caller (controller) maps that ValueError to HTTP 400; never let a bad
    client cursor reach the repo.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(ts_str), UUID(id_str)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"malformed cursor: {cursor!r}") from exc
