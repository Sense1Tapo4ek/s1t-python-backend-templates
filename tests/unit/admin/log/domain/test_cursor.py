import dataclasses

import pytest

from admin.log.domain import Cursor


class TestCursorType:
    def test_cursor_holds_inode_and_offset(self) -> None:
        """
        Given an inode and a byte offset,
        When a Cursor is constructed,
        Then both values are readable.
        """
        cur = Cursor(inode=42, offset=1024)

        assert cur.inode == 42
        assert cur.offset == 1024

    def test_cursor_is_frozen(self) -> None:
        """
        Given a Cursor,
        When mutating a field,
        Then FrozenInstanceError is raised.
        """
        cur = Cursor(inode=1, offset=0)

        with pytest.raises(dataclasses.FrozenInstanceError):
            cur.offset = 5  # type: ignore[misc]

    def test_cursor_equality_by_value(self) -> None:
        """
        Given two cursors with identical fields,
        When compared,
        Then they are equal.
        """
        assert Cursor(inode=7, offset=3) == Cursor(inode=7, offset=3)
