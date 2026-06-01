import pytest
from dishka import make_async_container

from db_example.config import DbExampleConfig
from db_example.provider import (
    DbExampleInfraProvider,
    PerRequestDbExampleProvider,
    PooledDbExampleProvider,
)
from shared.provider import SharedProvider


@pytest.mark.asyncio
async def test_infra_resolves(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("APP_NAME", "x")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    container = make_async_container(
        SharedProvider(), DbExampleInfraProvider(),
        PooledDbExampleProvider(), PerRequestDbExampleProvider(),
    )
    cfg = await container.get(DbExampleConfig)
    assert cfg.pool_size == 4
    await container.close()
