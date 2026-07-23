import pytest
from dishka import make_async_container

from db_example_litestar.config import DbExampleLitestarConfig
from db_example_litestar.provider import DbExampleLitestarProvider
from shared.provider import SharedProvider


@pytest.mark.asyncio
async def test_config_resolves(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Given the provider graph, When resolving config, Then schema_name is set."""
    monkeypatch.setenv("APP_NAME", "x")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    container = make_async_container(SharedProvider(), DbExampleLitestarProvider())
    cfg = await container.get(DbExampleLitestarConfig)
    assert cfg.schema_name == "db_example_litestar"
    await container.close()
