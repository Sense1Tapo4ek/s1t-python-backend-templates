from pathlib import Path

from admin.log.config import AdminLogConfig


class TestAdminLogConfig:
    def test_defaults(self, monkeypatch) -> None:
        """
        Given no LOG_ env overrides,
        When the config loads,
        Then file-tail defaults are present and DB/stream fields are gone.
        """
        for var in ("LOG_TAIL_LINES", "LOG_LOAD_MORE_LINES", "LOG_FOLLOW_POLL_MS",
                    "LOG_MAX_LINE_BYTES", "LOG_FILE_PATH"):
            monkeypatch.delenv(var, raising=False)

        cfg = AdminLogConfig()

        assert cfg.tail_lines == 200
        assert cfg.load_more_lines == 200
        assert cfg.follow_poll_ms == 250
        assert cfg.max_line_bytes > 0
        assert isinstance(cfg.file_path, Path)

        # removed fields must not exist
        for gone in ("log_retention_days", "log_batch_size", "log_db_reader_count",
                     "log_sse_queue_size", "log_stream_key",
                     "log_consumer_group", "log_events_channel"):
            assert not hasattr(cfg, gone), gone

    def test_file_path_defaults_under_log_dir(self) -> None:
        """
        Given default config,
        When reading file_path,
        Then it sits under the shared log_dir.
        """
        cfg = AdminLogConfig()
        assert cfg.file_path is not None
        assert cfg.file_path.parent == cfg.log_dir
