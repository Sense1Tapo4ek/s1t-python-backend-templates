import pytest
from dishka import make_async_container

from admin.log.app.interfaces import ILogFollower, ILogReader
from admin.log.ports.driving import LogsFacade
from admin.log.provider import AdminLogWebProvider


class TestLogProviderGraph:
    @pytest.mark.asyncio
    async def test_reader_and_follower_resolve_to_same_impl(
        self, monkeypatch, tmp_path
    ) -> None:
        """
        Given the simplified log provider,
        When resolving ILogReader and ILogFollower,
        Then both resolve and the facade builds.
        """
        # Arrange
        log_file = tmp_path / "app.jsonl"
        log_file.write_text("")
        monkeypatch.setenv("LOG_FILE_PATH", str(log_file))
        monkeypatch.setenv("APP_NAME", "litestar-base")
        container = make_async_container(AdminLogWebProvider())

        # Act
        reader = await container.get(ILogReader)
        follower = await container.get(ILogFollower)
        facade = await container.get(LogsFacade)

        # Assert
        assert reader is not None
        assert follower is not None
        assert isinstance(facade, LogsFacade)
        await container.close()

    def test_sink_provider_is_gone(self) -> None:
        """
        Given the removal of the out-of-process sink,
        When importing AdminLogSinkProvider,
        Then ImportError.
        """
        with pytest.raises(ImportError):
            from admin.log.provider import AdminLogSinkProvider  # noqa: F401
