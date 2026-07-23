import pytest
from litestar import Litestar
from litestar.testing import TestClient

from _e2e_constants import E2E_ADMIN_TOKEN
from root.entrypoints.api import create_app


def _build_app(
    tmp_path_factory: pytest.TempPathFactory,
    mp: pytest.MonkeyPatch,
    *,
    prom_public: bool = False,
) -> Litestar:
    volume = tmp_path_factory.mktemp("metrics_e2e")
    multiproc_dir = volume / "prometheus"
    multiproc_dir.mkdir()
    mp.setenv("PROMETHEUS_MULTIPROC_DIR", str(multiproc_dir))
    mp.setenv("APP_NAME", "test-service")
    mp.setenv("VOLUME_PATH", str(volume))
    mp.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)
    mp.setenv("METRICS_PROM_ENDPOINT_PUBLIC", "true" if prom_public else "false")
    return create_app()


class TestMetricsEndpointBasic:
    def test_metrics_returns_200_with_auth(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        """
        Given METRICS_PROM_ENDPOINT_PUBLIC=false (default),
        When GET /metrics is called with ADMIN auth,
        Then 200 is returned.
        """
        mp = pytest.MonkeyPatch()
        try:
            app = _build_app(tmp_path_factory, mp)
            with TestClient(app=app) as client:
                resp = client.get(
                    "/metrics",
                    headers={"Authorization": f"Bearer {E2E_ADMIN_TOKEN}"},
                )
            assert resp.status_code == 200
        finally:
            mp.undo()

    def test_metrics_content_type_is_text_plain(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """
        Given a running app,
        When GET /metrics is called with auth,
        Then content-type contains text/plain.
        """
        mp = pytest.MonkeyPatch()
        try:
            app = _build_app(tmp_path_factory, mp)
            with TestClient(app=app) as client:
                resp = client.get(
                    "/metrics",
                    headers={"Authorization": f"Bearer {E2E_ADMIN_TOKEN}"},
                )
            ct = resp.headers.get("content-type", "")
            assert "text/plain" in ct
        finally:
            mp.undo()

    def test_metrics_guarded_returns_401_without_auth(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """
        Given METRICS_PROM_ENDPOINT_PUBLIC=false,
        When GET /metrics is called WITHOUT auth,
        Then 401 or 403 is returned.
        """
        mp = pytest.MonkeyPatch()
        try:
            app = _build_app(tmp_path_factory, mp, prom_public=False)
            with TestClient(app=app) as client:
                resp = client.get("/metrics")
            assert resp.status_code in (401, 403)
        finally:
            mp.undo()

    def test_metrics_public_returns_200_without_auth(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """
        Given METRICS_PROM_ENDPOINT_PUBLIC=true,
        When GET /metrics is called WITHOUT auth,
        Then 200 is returned.
        """
        mp = pytest.MonkeyPatch()
        try:
            app = _build_app(tmp_path_factory, mp, prom_public=True)
            with TestClient(app=app) as client:
                resp = client.get("/metrics")
            assert resp.status_code == 200
        finally:
            mp.undo()


class TestMetricsBodyContent:
    def test_http_metric_names_appear_after_request(
        self, e2e_client: TestClient, e2e_auth_headers: dict[str, str]
    ) -> None:
        """
        Given the module-scoped app (warm from the e2e_client fixture),
        When GET /metrics is called with auth after a previous request,
        Then the Prometheus body contains HTTP metric names with the
        app_name prefix (dashes replaced by underscores).
        """
        resp = e2e_client.get("/metrics", headers=e2e_auth_headers)
        assert resp.status_code == 200
        body = resp.text
        prefix = "test_service"
        assert any(
            line.startswith(prefix) or f"# HELP {prefix}" in line for line in body.splitlines()
        ), f"Expected prefix '{prefix}' in /metrics body; got:\n{body[:500]}"
