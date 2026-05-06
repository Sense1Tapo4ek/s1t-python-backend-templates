from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend

from shared.adapters.driven.event_bus import ChannelsEventBus
from shared.config import BaseAppConfig
from shared.provider import SharedProvider


def _plugin() -> ChannelsPlugin:
    return ChannelsPlugin(
        backend=MemoryChannelsBackend(),
        arbitrary_channels_allowed=True,
    )


def test_shared_provider_provides_base_app_config() -> None:
    provider = SharedProvider(channels_plugin=_plugin())
    config = provider.provide_base_app_config()
    assert isinstance(config, BaseAppConfig)


def test_shared_provider_returns_supplied_plugin_instance() -> None:
    """The same plugin given at construction time must come out of `channels()`,
    so transport (Litestar) and publishers (DI) hit one backend."""
    plugin = _plugin()
    provider = SharedProvider(channels_plugin=plugin)
    assert provider.channels() is plugin


def test_shared_provider_event_bus_is_channels_backed() -> None:
    plugin = _plugin()
    provider = SharedProvider(channels_plugin=plugin)
    bus = provider.event_bus(plugin)
    assert isinstance(bus, ChannelsEventBus)
    # Structural Protocol conformance: the methods Litestar wiring depends on.
    for attr in ("publish", "subscribe", "start", "stop"):
        assert callable(getattr(bus, attr)), f"missing IEventBus member: {attr}"
