import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from ...ports.errors import LogReadError

_DEFAULT_CHUNK = 64 * 1024


@dataclass(slots=True, kw_only=True)
class LogFileSource:
    """Raw filesystem access to the JSONL log file.

    Owns the file-handle lifecycle, os.stat inode/size tracking, chunked
    reverse-read, and tail -F reopen-on-rotation. Wraps OSError into
    LogReadError. Returns raw text lines (LF-stripped, CR-tolerant) plus
    byte offsets and inode; entity mapping and cursor semantics live in
    the FileLogReader port. All reads discard a trailing partial line
    (bytes after the last newline) and decode UTF-8 only on complete
    newline boundaries.
    """

    path: Path
    chunk_bytes: int = _DEFAULT_CHUNK

    async def read_last_lines(self, limit: int) -> tuple[list[str], int, int]:
        return await asyncio.to_thread(self._read_last_lines, limit)

    async def read_lines_before(self, offset: int, limit: int) -> tuple[list[str], int]:
        return await asyncio.to_thread(self._read_lines_before, offset, limit)

    async def current_inode(self) -> int:
        return await asyncio.to_thread(self._current_inode)

    async def iter_all_lines(self) -> AsyncIterator[str]:
        # Snapshot semantics (spec section F): open once, stream the held fd
        # to EOF with no re-stat / reopen. Reads happen in a worker thread.
        try:
            fh = await asyncio.to_thread(open, self.path, "rb")
        except OSError as exc:
            raise LogReadError(path=str(self.path), reason=str(exc)) from exc
        try:
            buf = b""
            while True:
                chunk = await asyncio.to_thread(fh.read, self.chunk_bytes)
                if not chunk:
                    break
                buf += chunk
                *complete, buf = buf.split(b"\n")
                for raw in complete:
                    yield raw.decode("utf-8", "replace").rstrip("\r")
            # trailing bytes (buf) without newline are a partial line -> discard
        finally:
            await asyncio.to_thread(fh.close)

    async def iter_new_lines(self, poll_ms: int) -> AsyncIterator[str]:
        # tail -F: track (inode, position); on inode change or size-shrink,
        # drain the old fd to EOF then reopen the new path at its start.
        delay = poll_ms / 1000.0
        try:
            inode = await asyncio.to_thread(self._current_inode)
        except LogReadError:
            inode = -1
        pos = await asyncio.to_thread(self._initial_follow_pos)
        carry = b""
        while True:
            try:
                st = os.stat(self.path)
            except OSError:
                await asyncio.sleep(delay)
                continue

            rotated = st.st_ino != inode or st.st_size < pos
            if rotated:
                # drain remainder of the old inode before switching
                async for line in self._read_from(inode_pos=pos, prev_inode=inode):
                    yield line
                inode = st.st_ino
                pos = 0
                carry = b""

            if st.st_size > pos:
                data, pos, carry = await asyncio.to_thread(self._read_delta, pos, carry)
                for raw in data:
                    yield raw
            await asyncio.sleep(delay)

    # ---- sync internals (run in worker threads) ----

    def _current_inode(self) -> int:
        try:
            return os.stat(self.path).st_ino
        except OSError as exc:
            raise LogReadError(path=str(self.path), reason=str(exc)) from exc

    def _initial_follow_pos(self) -> int:
        try:
            return os.stat(self.path).st_size
        except OSError:
            return 0

    def _read_last_lines(self, limit: int) -> tuple[list[str], int, int]:
        try:
            inode = os.stat(self.path).st_ino
            with open(self.path, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                if size == 0:
                    return [], 0, inode
                buf = b""
                pos = size
                # Accumulate raw bytes from the end; only count newline
                # boundaries. Stop once we have limit+1 complete lines or
                # reach the start.
                while pos > 0:
                    read = min(self.chunk_bytes, pos)
                    seek_to = max(0, pos - read)
                    fh.seek(seek_to)
                    buf = fh.read(pos - seek_to) + buf
                    pos = seek_to
                    if buf.count(b"\n") >= limit + 1:
                        break
                lines, first_offset = self._tail_from_buffer(buf, pos, limit)
                return lines, first_offset, inode
        except OSError as exc:
            raise LogReadError(path=str(self.path), reason=str(exc)) from exc

    def _tail_from_buffer(self, buf: bytes, buf_start: int, limit: int) -> tuple[list[str], int]:
        # Discard trailing partial line: everything after the final newline.
        last_nl = buf.rfind(b"\n")
        if last_nl == -1:
            return [], buf_start
        body = buf[: last_nl + 1]
        # Split into complete lines; drop the empty final element.
        raw_lines = body.split(b"\n")[:-1]
        kept = raw_lines[-limit:] if limit < len(raw_lines) else raw_lines
        decoded = [b.decode("utf-8", "replace").rstrip("\r") for b in kept]
        # byte offset of the first kept line within the file
        dropped = raw_lines[: len(raw_lines) - len(kept)]
        first_offset = buf_start + sum(len(b) + 1 for b in dropped)
        return decoded, first_offset

    def _read_lines_before(self, offset: int, limit: int) -> tuple[list[str], int]:
        if offset <= 0:
            return [], 0
        try:
            with open(self.path, "rb") as fh:
                buf = b""
                pos = offset
                while pos > 0:
                    read = min(self.chunk_bytes, pos)
                    seek_to = max(0, pos - read)
                    fh.seek(seek_to)
                    buf = fh.read(pos - seek_to) + buf
                    pos = seek_to
                    if buf.count(b"\n") >= limit + 1:
                        break
                # Region [pos, offset) is the slice strictly before the cursor.
                # It ends exactly at a newline (cursor sits at a line start),
                # so there is no partial line to discard here.
                raw_lines = buf.split(b"\n")
                if raw_lines and raw_lines[-1] == b"":
                    raw_lines = raw_lines[:-1]
                kept = raw_lines[-limit:] if limit < len(raw_lines) else raw_lines
                decoded = [b.decode("utf-8", "replace").rstrip("\r") for b in kept]
                dropped = raw_lines[: len(raw_lines) - len(kept)]
                first_offset = pos + sum(len(b) + 1 for b in dropped)
                return decoded, first_offset
        except OSError as exc:
            raise LogReadError(path=str(self.path), reason=str(exc)) from exc

    def _read_delta(self, pos: int, carry: bytes) -> tuple[list[str], int, bytes]:
        # The file may vanish in the TOCTOU window between the caller's
        # os.stat and this read (rotation/deletion). Tolerate it the same
        # way the follow loop swallows OSError on stat: make no progress
        # and let the next poll observe the new state.
        try:
            with open(self.path, "rb") as fh:
                fh.seek(pos)
                chunk = fh.read()
        except OSError:
            return [], pos, carry
        data = carry + chunk
        *complete, rest = data.split(b"\n")
        lines = [b.decode("utf-8", "replace").rstrip("\r") for b in complete]
        # advance pos only past confirmed newlines; keep partial in carry
        consumed = len(data) - len(rest)
        return lines, pos + consumed, rest

    async def _read_from(self, *, inode_pos: int, prev_inode: int) -> AsyncIterator[str]:
        # Best-effort drain of the soon-to-be-replaced inode. self.path may
        # already resolve to the NEW inode (rename-mode rotation); reading it
        # at the old offset would emit garbage from an unrelated file. Only
        # drain when the path still points at prev_inode (truncate/size-shrink
        # in place). Otherwise the old inode is gone from the path and its
        # tail is tolerated lost (at-most-once across the rotation gap, E4).
        try:
            if os.stat(self.path).st_ino != prev_inode:
                return
            data, _, _ = await asyncio.to_thread(self._read_delta, inode_pos, b"")
        except OSError:
            return
        for line in data:
            yield line
