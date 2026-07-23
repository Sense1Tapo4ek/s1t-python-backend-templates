import pytest

from root.composition.container import build_container
from root.config import RootConfig


class TestRootContainer:
    @pytest.mark.asyncio
    async def test_container_provides_root_config(self) -> None:
        """
        Given the root Dishka container,
        When RootConfig is resolved,
        Then it carries a redis:// Valkey URL.
        """
        # Arrange
        container = build_container()

        # Act
        try:
            config = await container.get(RootConfig)
        finally:
            await container.close()

        # Assert
        assert isinstance(config, RootConfig)
        assert config.valkey_url.startswith("redis://")
