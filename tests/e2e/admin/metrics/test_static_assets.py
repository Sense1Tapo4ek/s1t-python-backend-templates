from litestar.testing import TestClient


class TestMetricsStaticAssets:
    def test_style_css_served(
        self, e2e_client: TestClient, e2e_auth_headers: dict[str, str]
    ) -> None:
        """
        Given METRICS_ENABLED=true (default e2e),
        When GET /admin/metrics/static/style.css is called,
        Then 200 with text/css and known selector in body.
        """
        resp = e2e_client.get(
            "/admin/metrics/static/style.css", headers=e2e_auth_headers
        )
        assert resp.status_code == 200
        assert "text/css" in resp.headers["content-type"]
        assert ".modcard" in resp.text

    def test_overview_js_served(
        self, e2e_client: TestClient, e2e_auth_headers: dict[str, str]
    ) -> None:
        """
        Given METRICS_ENABLED=true (default e2e),
        When GET /admin/metrics/static/overview.js is called,
        Then 200 with javascript content-type and known function name.
        """
        resp = e2e_client.get(
            "/admin/metrics/static/overview.js", headers=e2e_auth_headers
        )
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]
        assert "applyOverview" in resp.text
