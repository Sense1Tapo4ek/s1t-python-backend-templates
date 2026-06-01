import pytest
from dishka import make_async_container

from db_example_sddd.config import DbExampleSdddConfig
from db_example_sddd.provider import (
    DbExampleSdddInfraProvider,
    PerRequestDbExampleSdddProvider,
    PooledDbExampleSdddProvider,
)
from shared.provider import SharedProvider


@pytest.mark.asyncio
async def test_infra_resolves(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("APP_NAME", "x")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    container = make_async_container(
        SharedProvider(), DbExampleSdddInfraProvider(),
        PooledDbExampleSdddProvider(), PerRequestDbExampleSdddProvider(),
    )
    cfg = await container.get(DbExampleSdddConfig)
    assert cfg.pool_size == 4
    await container.close()
