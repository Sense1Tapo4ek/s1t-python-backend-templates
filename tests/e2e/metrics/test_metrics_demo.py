"""E2E for the metrics demo endpoint and the custom demo metrics.

PROMETHEUS_MULTIPROC_DIR is intentionally NOT set here. The template runs
with a single Uvicorn master (APP_WORKERS=1 default); in the test process
prometheus_client is already imported before any per-test env patch, so
metric objects (Counter / Gauge / Histogram) are bound to the in-process
REGISTRY, not to mmap files. Setting PROMETHEUS_MULTIPROC_DIR after import
causes PrometheusController to read empty mmap files while the actual
values live in REGISTRY -- yielding an empty scrape body.

The module-scoped e2e_client fixture (used by test_metrics_endpoint.py
body-content tests) follows the same convention: it does not set
PROMETHEUS_MULTIPROC_DIR, letting the default REGISTRY serve scrape
requests.
"""

import pytest
from litestar.testing import TestClient

from _e2e_constants import E2E_ADMIN_TOKEN
from root.entrypoints.api import create_app


def _build_app(tmp_path_factory: pytest.TempPathFactory, mp: pytest.MonkeyPatch) -> object:
    volume = tmp_path_factory.mktemp("metrics_demo_e2e")
    # Do not set PROMETHEUS_MULTIPROC_DIR: prometheus_client is already imported
    # in this process and bound to in-process REGISTRY. PrometheusController
    # checks os.environ at request time; if the var is present it uses
    # MultiProcessCollector (reads empty mmap) instead of REGISTRY.
    mp.setenv("APP_NAME", "test-service")
    mp.setenv("VOLUME_PATH", str(volume))
    mp.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)
    return create_app()


def test_demo_emits_then_metrics_exposes_widget_series(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """
    Given the app,
    When GET /metrics-demo (no auth) then GET /metrics (admin auth),
    Then the demo endpoint returns 200 and the body exposes the three widget_* series.
    """
    mp = pytest.MonkeyPatch()
    try:
        app = _build_app(tmp_path_factory, mp)
        with TestClient(app=app) as client:
            demo = client.get("/metrics-demo")
            assert demo.status_code == 200
            assert "widget_render_total" in demo.json()["emitted"]

            scrape = client.get(
                "/metrics", headers={"Authorization": f"Bearer {E2E_ADMIN_TOKEN}"}
            )
            assert scrape.status_code == 200
            body = scrape.text
            assert "widget_render_total" in body
            assert "widget_queue_depth" in body
            assert "widget_render_seconds" in body
    finally:
        mp.undo()
