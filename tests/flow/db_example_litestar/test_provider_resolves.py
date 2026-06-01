import pytest
from dishka import make_async_container

from db_example_litestar.config import DbExampleLitestarConfig
from db_example_litestar.provider import DbExampleLitestarProvider


@pytest.mark.asyncio
async def test_config_resolves(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("APP_NAME", "x")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    container = make_async_container(DbExampleLitestarProvider())
    cfg = await container.get(DbExampleLitestarConfig)
    assert cfg.db_path is not None
    await container.close()
