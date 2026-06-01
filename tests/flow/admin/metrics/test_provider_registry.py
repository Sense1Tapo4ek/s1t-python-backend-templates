import pytest
from dishka import Provider, Scope, make_async_container, provide
from prometheus_client import REGISTRY

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


@pytest.fixture(autouse=True)
def _isolated_registry():
    """Tear down Prometheus collectors added by each test to avoid duplicate registration."""
    snapshot = list(REGISTRY._collector_to_names.keys())
    yield
    for c in list(REGISTRY._collector_to_names.keys()):
        if c not in snapshot:
            REGISTRY.unregister(c)


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
            SharedProvider(),
            AdminMetricsProvider(),
            _StubProvider(),
        )
        try:
            reg = await container.get(IModulePluginRegistry)
            assert any(p.slug == "stub" for p in reg.all())
        finally:
            await container.close()


class TestBuiltInPlugins:
    async def test_workers_plugin_registered(self) -> None:
        """
        Given the metrics provider + shared provider,
        When the container resolves the registry,
        Then 'workers' is among the plugin slugs.
        """
        container = make_async_container(
            SharedProvider(),
            AdminMetricsProvider(),
        )
        try:
            reg = await container.get(IModulePluginRegistry)
            slugs = [p.slug for p in reg.all()]
            assert "workers" in slugs
        finally:
            await container.close()

    async def test_http_plugin_registered(self) -> None:
        """
        Given the metrics provider + shared provider,
        When the container resolves the registry,
        Then 'http' is among the plugin slugs.
        """
        container = make_async_container(
            SharedProvider(),
            AdminMetricsProvider(),
        )
        try:
            reg = await container.get(IModulePluginRegistry)
            slugs = [p.slug for p in reg.all()]
            assert "http" in slugs
        finally:
            await container.close()
