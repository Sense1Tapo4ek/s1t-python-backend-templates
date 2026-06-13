import asyncio
import os
from pathlib import Path

import orjson
import pytest

from admin.log.adapters.driven.log_file_source import LogFileSource
from admin.log.ports.errors import LogReadError


def _line(event: str) -> str:
    return orjson.dumps({"event": event}).decode()


def _write_lines(path: Path, events: list[str]) -> None:
    path.write_text("".join(_line(e) + "\n" for e in events), encoding="utf-8")


class TestReadLastLines:
    @pytest.mark.asyncio
    async def test_returns_last_n_in_order(self, tmp_path: Path) -> None:
        """
        Given a file with five lines,
        When reading the last three,
        Then the three newest are returned oldest-first.
        """
        path = tmp_path / "app.jsonl"
        _write_lines(path, ["a", "b", "c", "d", "e"])
        src = LogFileSource(path=path, chunk_bytes=8)

        lines, offset, inode = await src.read_last_lines(3)

        assert [orjson.loads(line)["event"] for line in lines] == ["c", "d", "e"]
        assert inode == os.stat(path).st_ino
        assert offset > 0

    @pytest.mark.asyncio
    async def test_limit_larger_than_file_returns_all(self, tmp_path: Path) -> None:
        """
        Given a file with two lines,
        When reading more than exist,
        Then all lines are returned and offset is zero.
        """
        path = tmp_path / "app.jsonl"
        _write_lines(path, ["a", "b"])
        src = LogFileSource(path=path, chunk_bytes=4)

        lines, offset, _ = await src.read_last_lines(10)

        assert [orjson.loads(line)["event"] for line in lines] == ["a", "b"]
        assert offset == 0

    @pytest.mark.asyncio
    async def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        """
        Given an empty file,
        When reading the tail,
        Then no lines and a zero offset are returned.
        """
        path = tmp_path / "app.jsonl"
        path.write_text("", encoding="utf-8")
        src = LogFileSource(path=path, chunk_bytes=8)

        lines, offset, inode = await src.read_last_lines(5)

        assert lines == []
        assert offset == 0
        assert inode == os.stat(path).st_ino

    @pytest.mark.asyncio
    async def test_trailing_partial_line_discarded(self, tmp_path: Path) -> None:
        """
        Given a file whose last line lacks a newline (mid-append),
        When reading the tail,
        Then the partial line is not returned.
        """
        path = tmp_path / "app.jsonl"
        path.write_text(
            _line("a") + "\n" + _line("b") + "\n" + '{"event":"partial"', encoding="utf-8"
        )
        src = LogFileSource(path=path, chunk_bytes=8)

        lines, _, _ = await src.read_last_lines(5)

        assert [orjson.loads(line)["event"] for line in lines] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_utf8_multibyte_across_chunks(self, tmp_path: Path) -> None:
        """
        Given lines with multibyte UTF-8 that straddle chunk boundaries,
        When read with a tiny chunk size,
        Then decoding is correct.
        """
        path = tmp_path / "app.jsonl"
        _write_lines(path, ["café", "naïve", "日本語"])
        src = LogFileSource(path=path, chunk_bytes=3)

        lines, _, _ = await src.read_last_lines(3)

        assert [orjson.loads(line)["event"] for line in lines] == ["café", "naïve", "日本語"]

    @pytest.mark.asyncio
    async def test_missing_file_raises_log_read_error(self, tmp_path: Path) -> None:
        """
        Given a path that does not exist,
        When reading the tail,
        Then LogReadError is raised.
        """
        src = LogFileSource(path=tmp_path / "nope.jsonl", chunk_bytes=8)

        with pytest.raises(LogReadError):
            await src.read_last_lines(3)


class TestReadLinesBefore:
    @pytest.mark.asyncio
    async def test_reads_strictly_before_offset(self, tmp_path: Path) -> None:
        """
        Given the tail cursor of a file,
        When reading lines before it,
        Then earlier lines are returned oldest-first.
        """
        path = tmp_path / "app.jsonl"
        _write_lines(path, ["a", "b", "c", "d", "e"])
        src = LogFileSource(path=path, chunk_bytes=8)

        _, tail_offset, _ = await src.read_last_lines(2)  # cursor before "d"
        lines, offset = await src.read_lines_before(tail_offset, 2)

        assert [orjson.loads(line)["event"] for line in lines] == ["b", "c"]
        assert offset < tail_offset

    @pytest.mark.asyncio
    async def test_before_start_returns_empty(self, tmp_path: Path) -> None:
        """
        Given offset zero (start of file),
        When reading before it,
        Then no lines are returned.
        """
        path = tmp_path / "app.jsonl"
        _write_lines(path, ["a", "b"])
        src = LogFileSource(path=path, chunk_bytes=8)

        lines, offset = await src.read_lines_before(0, 5)

        assert lines == []
        assert offset == 0


class TestIterAllLines:
    @pytest.mark.asyncio
    async def test_streams_snapshot_oldest_first(self, tmp_path: Path) -> None:
        """
        Given a file with three lines,
        When streaming all lines,
        Then they arrive oldest-first and the trailing partial is skipped.
        """
        path = tmp_path / "app.jsonl"
        path.write_text(_line("a") + "\n" + _line("b") + "\n" + "partial", encoding="utf-8")
        src = LogFileSource(path=path, chunk_bytes=8)

        out = [orjson.loads(line)["event"] async for line in src.iter_all_lines()]

        assert out == ["a", "b"]


class TestFollow:
    @pytest.mark.asyncio
    async def test_yields_appended_lines(self, tmp_path: Path) -> None:
        """
        Given a follow loop on a file,
        When new lines are appended,
        Then they are yielded.
        """
        path = tmp_path / "app.jsonl"
        _write_lines(path, ["a"])
        src = LogFileSource(path=path, chunk_bytes=64)

        agen = src.iter_new_lines(poll_ms=10)
        collected: list[str] = []

        async def consume() -> None:
            async for line in agen:
                collected.append(orjson.loads(line)["event"])
                if len(collected) == 2:
                    return

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(_line("b") + "\n")
            fh.write(_line("c") + "\n")
        await asyncio.wait_for(task, timeout=2.0)

        assert collected == ["b", "c"]

    @pytest.mark.asyncio
    async def test_follow_survives_inode_rotation(self, tmp_path: Path) -> None:
        """
        Given a follow loop,
        When the file is renamed away and recreated (create-mode rotation),
        Then lines written to the new file are still yielded.
        """
        path = tmp_path / "app.jsonl"
        _write_lines(path, ["old"])
        src = LogFileSource(path=path, chunk_bytes=64)

        agen = src.iter_new_lines(poll_ms=10)
        collected: list[str] = []

        async def consume() -> None:
            async for line in agen:
                collected.append(orjson.loads(line)["event"])
                if collected == ["fresh"]:
                    return

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        path.rename(tmp_path / "app.jsonl.1")
        _write_lines(path, ["fresh"])
        await asyncio.wait_for(task, timeout=2.0)

        assert collected == ["fresh"]

    @pytest.mark.asyncio
    async def test_follow_survives_file_deletion_mid_stream(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given a follow loop where the file vanishes in the TOCTOU window
        between os.stat and the offloaded read,
        When the file is later recreated and appended,
        Then the loop does not crash and resumes yielding the new lines.
        """
        path = tmp_path / "app.jsonl"
        _write_lines(path, ["a"])
        src = LogFileSource(path=path, chunk_bytes=64)

        # Simulate the TOCTOU race: os.stat reports the file present, then
        # _read_delta's open() fails because the file vanished in the gap.
        # Patch the module-level open so the FIRST read raises OSError; the
        # real _read_delta must swallow it and the loop must not crash.
        import builtins

        import admin.log.adapters.driven.log_file_source as mod

        real_open = builtins.open
        calls = {"n": 0}

        def flaky_open(file, *args, **kwargs):
            if str(file) == str(path):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise FileNotFoundError(2, "No such file or directory", str(path))
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr(mod, "open", flaky_open, raising=False)

        agen = src.iter_new_lines(poll_ms=10)
        collected: list[str] = []

        async def consume() -> None:
            async for line in agen:
                collected.append(orjson.loads(line)["event"])
                if "resumed" in collected:
                    return

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        # First append triggers the flaky (vanished) read; the loop must
        # not crash and must make no progress (pos unchanged).
        with path.open("a", encoding="utf-8") as fh:
            fh.write(_line("lost") + "\n")
        await asyncio.sleep(0.05)
        # Second append: the real read now succeeds and recovers both the
        # earlier-skipped line and the new one (at-least-once).
        with path.open("a", encoding="utf-8") as fh:
            fh.write(_line("resumed") + "\n")
        await asyncio.wait_for(task, timeout=2.0)

        assert calls["n"] >= 2  # the flaky read was exercised
        assert collected[-1] == "resumed"  # loop survived and resumed
        assert "lost" in collected  # skipped line recovered on retry

    @pytest.mark.asyncio
    async def test_follow_survives_truncation(self, tmp_path: Path) -> None:
        """
        Given a follow loop,
        When the file is truncated in place (copytruncate),
        Then subsequent appends are yielded.
        """
        path = tmp_path / "app.jsonl"
        _write_lines(path, ["one", "two"])
        src = LogFileSource(path=path, chunk_bytes=64)

        agen = src.iter_new_lines(poll_ms=10)
        collected: list[str] = []

        async def consume() -> None:
            async for line in agen:
                collected.append(orjson.loads(line)["event"])
                if collected == ["after"]:
                    return

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        path.write_text(_line("after") + "\n", encoding="utf-8")  # truncate + rewrite
        await asyncio.wait_for(task, timeout=2.0)

        assert collected == ["after"]
