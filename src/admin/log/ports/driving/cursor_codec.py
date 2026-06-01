import base64
import binascii

from ...domain import Cursor


def encode_cursor(cursor: Cursor) -> str:
    raw = f"{cursor.inode}:{cursor.offset}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(token: str) -> Cursor:
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"malformed cursor token: {token!r}") from exc
    inode_str, _, offset_str = raw.partition(":")
    if not _ or not inode_str or not offset_str:
        raise ValueError(f"malformed cursor token: {token!r}")
    try:
        return Cursor(inode=int(inode_str), offset=int(offset_str))
    except ValueError as exc:
        raise ValueError(f"malformed cursor token: {token!r}") from exc
