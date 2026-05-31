from pathlib import Path

import orjson
import pytest

from admin.log.adapters.driven.files.log_file_source import LogFileSource
from admin.log.domain import Cursor
from admin.log.ports.driven.repos.file_log_reader import FileLogReader


def _line(event: str, **extra: object) -> str:
    return orjson.dumps({"level": "INFO", "event": event, **extra}).decode()


def _write(path: Path, events: list[str]) -> None:
    path.write_text("".join(_line(e) + "\n" for e in events), encoding="utf-8")


def _reader(path: Path) -> FileLogReader:
    return FileLogReader(_source=LogFileSource(path=path, chunk_bytes=16))


class TestReadTail:
    @pytest.mark.asyncio
    async def test_returns_entities_chronological_with_cursor(self, tmp_path: Path) -> None:
        """
        Given a file with four lines,
        When reading the tail of two,
        Then two entities (oldest-first) and a cursor are returned.
        """
        path = tmp_path / "app.jsonl"
        _write(path, ["a", "b", "c", "d"])
        reader = _reader(path)

        entries, cursor = await reader.read_tail(2)

        assert [e.event for e in entries] == ["c", "d"]
        assert isinstance(cursor, Cursor)
        assert cursor.offset > 0

    @pytest.mark.asyncio
    async def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        """
        Given a file with a non-JSON line between valid lines,
        When reading the tail,
        Then the malformed line is skipped, not raised.
        """
        path = tmp_path / "app.jsonl"
        path.write_text(_line("a") + "\n" + "garbage\n" + _line("b") + "\n", encoding="utf-8")
        reader = _reader(path)

        entries, _ = await reader.read_tail(10)

        assert [e.event for e in entries] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_empty_file_returns_empty_cursor(self, tmp_path: Path) -> None:
        """
        Given an empty file,
        When reading the tail,
        Then no entries and a zero-offset cursor are returned.
        """
        path = tmp_path / "app.jsonl"
        path.write_text("", encoding="utf-8")
        reader = _reader(path)

        entries, cursor = await reader.read_tail(5)

        assert entries == []
        assert cursor.offset == 0


class TestReadBefore:
    @pytest.mark.asyncio
    async def test_reads_earlier_page(self, tmp_path: Path) -> None:
        """
        Given the tail cursor,
        When reading before it,
        Then earlier entities are returned with a smaller cursor.
        """
        path = tmp_path / "app.jsonl"
        _write(path, ["a", "b", "c", "d"])
        reader = _reader(path)

        _, tail_cursor = await reader.read_tail(2)
        entries, prev_cursor = await reader.read_before(tail_cursor, 2)

        assert [e.event for e in entries] == ["a", "b"]
        assert prev_cursor.offset <= tail_cursor.offset

    @pytest.mark.asyncio
    async def test_inode_mismatch_returns_sentinel(self, tmp_path: Path) -> None:
        """
        Given a cursor whose inode no longer matches the live file,
        When reading before it,
        Then an empty page with the same cursor is returned (rotation sentinel).
        """
        path = tmp_path / "app.jsonl"
        _write(path, ["a", "b"])
        reader = _reader(path)
        stale = Cursor(inode=999_999_999, offset=10)

        entries, cursor = await reader.read_before(stale, 5)

        assert entries == []
        assert cursor == stale


class TestStreamAll:
    @pytest.mark.asyncio
    async def test_yields_raw_lines(self, tmp_path: Path) -> None:
        """
        Given a file with two lines,
        When streaming all,
        Then raw JSONL strings (not entities) are yielded oldest-first.
        """
        path = tmp_path / "app.jsonl"
        _write(path, ["a", "b"])
        reader = _reader(path)

        out = [line async for line in reader.stream_all()]

        assert [orjson.loads(line)["event"] for line in out] == ["a", "b"]


class TestFollow:
    @pytest.mark.asyncio
    async def test_yields_entities(self, tmp_path: Path) -> None:
        """
        Given a follow loop,
        When a line is appended,
        Then a parsed entity is yielded.
        """
        import asyncio

        path = tmp_path / "app.jsonl"
        _write(path, ["a"])
        reader = _reader(path)

        agen = reader.follow(poll_ms=10)
        got: list[str] = []

        async def consume() -> None:
            async for entry in agen:
                got.append(entry.event)
                return

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(_line("b") + "\n")
        await asyncio.wait_for(task, timeout=2.0)

        assert got == ["b"]
