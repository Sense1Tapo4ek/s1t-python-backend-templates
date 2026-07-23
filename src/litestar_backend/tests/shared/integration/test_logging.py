import logging
from pathlib import Path

import orjson
import pytest
import structlog

from shared.logging import configure_structlog


@pytest.fixture
def _reset_logging():
    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers = []
    yield
    for h in root.handlers:
        h.close()
    root.handlers = saved
    structlog.reset_defaults()


class TestConfigureStructlog:
    def test_writes_one_json_line_to_file(self, tmp_path: Path, _reset_logging) -> None:
        """
        Given structlog configured with a file path,
        When a log record is emitted,
        Then the file contains exactly one JSON object on one line.
        """
        log_file = tmp_path / "app.jsonl"
        configure_structlog(app_name="test", log_file_path=log_file, max_line_bytes=10_000)

        structlog.get_logger("t").info("hello", user_id=7)

        for h in logging.getLogger().handlers:
            h.flush()
        content = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(content) == 1
        data = orjson.loads(content[0])
        assert data["event"] == "hello"
        assert data["level"] == "info"
        assert data["user_id"] == 7

    def test_truncates_oversized_line(self, tmp_path: Path, _reset_logging) -> None:
        """
        Given a small max_line_bytes,
        When a record with a huge field is emitted,
        Then the written line does not exceed the cap (plus the newline).
        """
        log_file = tmp_path / "app.jsonl"
        configure_structlog(app_name="test", log_file_path=log_file, max_line_bytes=200)

        structlog.get_logger("t").info("big", blob="x" * 5000)

        for h in logging.getLogger().handlers:
            h.flush()
        line = log_file.read_text(encoding="utf-8").splitlines()[0]
        assert len(line.encode("utf-8")) <= 200
