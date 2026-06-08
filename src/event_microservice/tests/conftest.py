import os
from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session")
def valkey_url() -> Iterator[str]:
    env = os.getenv("VALKEY_URL")
    if env:
        yield env
        return

    from testcontainers.redis import RedisContainer

    with RedisContainer("valkey/valkey:8") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"
