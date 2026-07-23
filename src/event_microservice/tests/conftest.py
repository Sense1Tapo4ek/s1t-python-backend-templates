import os
from collections.abc import Iterator

import pytest

_LEVELS = ("unit", "flow", "integration", "e2e")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Tag each test with its pyramid level from the path.

    Layout is `tests/<context>/<level>/...`, so the level is a path segment;
    marking lets the Taskfile select a level with `pytest -m <level>`.
    """
    for item in items:
        path = str(item.path).replace(os.sep, "/")
        for level in _LEVELS:
            if f"/{level}/" in path:
                item.add_marker(getattr(pytest.mark, level))
                break


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
