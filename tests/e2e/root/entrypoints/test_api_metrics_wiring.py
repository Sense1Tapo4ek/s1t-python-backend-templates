"""E2E: Prometheus metrics endpoint wired in create_app()."""

from litestar.testing import TestClient


class TestMetricsEndpointWired:
    def test_metrics_endpoint_returns_text_plain(
        self,
        e2e_client: TestClient,
        e2e_auth_headers: dict[str, str],
    ) -> None:
        """
        Given the app started with Prometheus middleware wired,
        When GET /metrics is called with ADMIN credentials,
        Then 200 is returned with Prometheus text content type.
        """
        resp = e2e_client.get("/metrics", headers=e2e_auth_headers)
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
