"""Matrix tests for /metrics auth + /admin/metrics enabled gating.

Each test builds its own Litestar app with bespoke env so we can flip
METRICS_ENABLED and METRICS_PROM_ENDPOINT_PUBLIC independently. Uses
pytest.MonkeyPatch at function scope; does NOT request the module-scoped
e2e_client to avoid env contention.
"""

from collections.abc import Iterator

import pytest
from litestar import Litestar
from litestar.testing import TestClient
from prometheus_client import REGISTRY

from _e2e_constants import E2E_ADMIN_TOKEN
from root.entrypoints.api import create_app


@pytest.fixture
def _isolated_prom_registry() -> Iterator[None]:
    snapshot = set(REGISTRY._collector_to_names.keys())
    yield
    for c in list(REGISTRY._collector_to_names.keys()):
        if c not in snapshot:
            REGISTRY.unregister(c)


def _build_app(
    tmp_path_factory: pytest.TempPathFactory,
    mp: pytest.MonkeyPatch,
    *,
    enabled: bool,
    prom_public: bool,
) -> Litestar:
    mp.setenv("APP_NAME", "test-service")
    mp.setenv("VOLUME_PATH", str(tmp_path_factory.mktemp("matrix")))
    mp.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)
    mp.setenv("METRICS_ENABLED", "true" if enabled else "false")
    mp.setenv("METRICS_PROM_ENDPOINT_PUBLIC", "true" if prom_public else "false")
    return create_app()


@pytest.mark.usefixtures("_isolated_prom_registry")
class TestPromEndpointAuthMatrix:
    def test_prom_public_returns_200_without_auth(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """
        Given METRICS_PROM_ENDPOINT_PUBLIC=true,
        When GET /metrics is called WITHOUT auth,
        Then 200 is returned.
        """
        mp = pytest.MonkeyPatch()
        try:
            app = _build_app(tmp_path_factory, mp, enabled=True, prom_public=True)
            with TestClient(app=app) as client:
                resp = client.get("/metrics")
            assert resp.status_code == 200
        finally:
            mp.undo()

    def test_prom_guarded_blocks_anonymous(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """
        Given METRICS_PROM_ENDPOINT_PUBLIC=false (default),
        When GET /metrics is called WITHOUT auth,
        Then 401 or 403 is returned.
        """
        mp = pytest.MonkeyPatch()
        try:
            app = _build_app(tmp_path_factory, mp, enabled=True, prom_public=False)
            with TestClient(app=app) as client:
                resp = client.get("/metrics")
            assert resp.status_code in (401, 403)
        finally:
            mp.undo()


@pytest.mark.usefixtures("_isolated_prom_registry")
class TestUiEnabledGating:
    def test_ui_404_when_metrics_disabled(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """
        Given METRICS_ENABLED=false,
        When GET /admin/metrics/ is called as ADMIN,
        Then 404 is returned (controller not registered).
        """
        mp = pytest.MonkeyPatch()
        try:
            app = _build_app(tmp_path_factory, mp, enabled=False, prom_public=False)
            with TestClient(app=app) as client:
                resp = client.get(
                    "/admin/metrics/",
                    headers={"Authorization": f"Bearer {E2E_ADMIN_TOKEN}"},
                )
            assert resp.status_code == 404
        finally:
            mp.undo()

    def test_prom_still_up_when_ui_disabled(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """
        Given METRICS_ENABLED=false,
        When GET /metrics is called as ADMIN,
        Then 200 is still returned — /metrics is independent of UI flag.
        """
        mp = pytest.MonkeyPatch()
        try:
            app = _build_app(tmp_path_factory, mp, enabled=False, prom_public=False)
            with TestClient(app=app) as client:
                resp = client.get(
                    "/metrics",
                    headers={"Authorization": f"Bearer {E2E_ADMIN_TOKEN}"},
                )
            assert resp.status_code == 200
        finally:
            mp.undo()
