from shared.config import BaseAppConfig
from shared.provider import SharedProvider


def test_shared_provider_provides_base_app_config() -> None:
    provider = SharedProvider()
    config = provider.provide_base_app_config()
    assert isinstance(config, BaseAppConfig)
