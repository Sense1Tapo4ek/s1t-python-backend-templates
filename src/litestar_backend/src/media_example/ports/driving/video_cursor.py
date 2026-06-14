import base64
import binascii
from datetime import datetime
from uuid import UUID


def encode_cursor(uploaded_at: datetime, video_id: UUID) -> str:
    """Opaque, URL-safe token encoding the keyset position (uploaded_at, id)."""
    raw = f"{uploaded_at.isoformat()}|{video_id}".encode()
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
