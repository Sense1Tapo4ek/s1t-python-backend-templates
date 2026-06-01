import pytest


class TestChannelsRemoved:
    def test_channels_event_bus_gone(self) -> None:
        """
        Given the event bus removal,
        When importing ChannelsEventBus,
        Then ImportError.
        """
        with pytest.raises(ImportError):
            from shared.adapters.driven.event_bus import (  # noqa: F401
                ChannelsEventBus,
            )

    def test_app_builds_without_channels(self, monkeypatch, tmp_path) -> None:
        """
        Given no ChannelsPlugin,
        When create_app() runs,
        Then the app object builds and has no channels_plugin in state.
        """
        log_file = tmp_path / "app.jsonl"
        log_file.write_text("")
        monkeypatch.setenv("LOG_FILE_PATH", str(log_file))
        monkeypatch.setenv("APP_NAME", "litestar-base")
        from root.entrypoints.api import create_app

        app = create_app()
        assert not hasattr(app.state, "channels_plugin")
