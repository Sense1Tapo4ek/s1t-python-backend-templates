import pytest

from admin.log.domain import Cursor
from admin.log.ports.driving.cursor_codec import decode_cursor, encode_cursor


class TestCursorCodec:
    def test_roundtrip(self) -> None:
        """
        Given a Cursor(inode, offset),
        When encoded then decoded,
        Then the original Cursor is recovered.
        """
        # Arrange
        cursor = Cursor(inode=123456, offset=4096)

        # Act
        token = encode_cursor(cursor)
        back = decode_cursor(token)

        # Assert
        assert isinstance(token, str)
        assert back == cursor

    def test_decode_rejects_garbage(self) -> None:
        """
        Given a malformed token,
        When decoding,
        Then ValueError is raised (controller maps to 400).
        """
        # Act / Assert
        with pytest.raises(ValueError):
            decode_cursor("!!!not-base64!!!")
        with pytest.raises(ValueError):
            decode_cursor("Zm9vYmFy")  # "foobar", no colon
