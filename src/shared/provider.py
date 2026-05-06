from dishka import Provider, Scope, provide
from litestar.channels import ChannelsPlugin

from shared.adapters.driven.event_bus import ChannelsEventBus
from shared.app import IEventBus
from shared.config import BaseAppConfig


class SharedProvider(Provider):
    """Cross-context bindings.

    `channels_plugin` is created in the entrypoint (`create_app`) and shared
    between Litestar's plugin slot and the DI container so producers and
    subscribers all hit the same backend instance.
    """

    scope = Scope.APP

    def __init__(self, *, channels_plugin: ChannelsPlugin) -> None:
        super().__init__()
        self._channels_plugin = channels_plugin

    @provide
    def provide_base_app_config(self) -> BaseAppConfig:
        return BaseAppConfig()

    @provide
    def channels(self) -> ChannelsPlugin:
        return self._channels_plugin

    @provide(provides=IEventBus)
    def event_bus(self, channels: ChannelsPlugin) -> ChannelsEventBus:
        return ChannelsEventBus(_channels=channels)
