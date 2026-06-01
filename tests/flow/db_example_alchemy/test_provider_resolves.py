import pytest
from dishka import make_async_container

from db_example_alchemy.config import DbExampleAlchemyConfig
from db_example_alchemy.provider import DbExampleAlchemyProvider


@pytest.mark.asyncio
async def test_config_resolves(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("APP_NAME", "x")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    container = make_async_container(DbExampleAlchemyProvider())
    cfg = await container.get(DbExampleAlchemyConfig)
    assert cfg.db_path is not None
    await container.close()
