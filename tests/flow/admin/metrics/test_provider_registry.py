import pytest
from dishka import Provider, Scope, make_async_container, provide
from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend

from admin.metrics.app.interfaces import (
    IMetricsModulePlugin,
    IModulePluginRegistry,
)
from admin.metrics.domain import (
    MetricKvVo,
    ModuleDetailVo,
    ModuleSummaryVo,
    Severity,
)
from admin.metrics.provider import AdminMetricsProvider
from shared.provider import SharedProvider

pytestmark = pytest.mark.asyncio


def _channels_plugin() -> ChannelsPlugin:
    return ChannelsPlugin(
        backend=MemoryChannelsBackend(),
        arbitrary_channels_allowed=True,
    )


class _Stub:
    name = "STUB"
    slug = "stub"
    description = ""

    async def summary(self) -> ModuleSummaryVo:
        return ModuleSummaryVo(
            slug=self.slug, name=self.name,
            kvs=(MetricKvVo(label="x", value="1", severity=Severity.OK),),
        )

    async def detail(self) -> ModuleDetailVo:
        return ModuleDetailVo(slug=self.slug, name=self.name, sections=())

    def render_detail_html(self, _d: ModuleDetailVo) -> str:
        return "<p>stub</p>"


class _StubProvider(Provider):
    scope = Scope.APP

    @provide(provides=IMetricsModulePlugin)
    def stub(self) -> _Stub:
        return _Stub()


class TestRegistryCollectsExternalPlugins:
    async def test_external_plugin_appears_in_registry(self) -> None:
        """
        Given an external Provider providing IMetricsModulePlugin,
        When the container resolves IModulePluginRegistry,
        Then the external plugin is in registry.all().
        """
        container = make_async_container(
            SharedProvider(channels_plugin=_channels_plugin()),
            AdminMetricsProvider(),
            _StubProvider(),
        )
        try:
            reg = await container.get(IModulePluginRegistry)
            assert any(p.slug == "stub" for p in reg.all())
        finally:
            await container.close()
