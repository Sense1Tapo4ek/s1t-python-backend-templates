from litestar.testing import TestClient


class TestModuleDetailEndpoint:
    def test_module_detail_html_returns_plugin_html(
        self, e2e_client: TestClient, e2e_auth_headers: dict[str, str]
    ) -> None:
        """
        Given a registered plugin slug ('http'),
        When GET /admin/metrics/http is called as ADMIN,
        Then HTML page wraps the plugin's render_detail_html output.
        """
        resp = e2e_client.get("/admin/metrics/http", headers=e2e_auth_headers)
        assert resp.status_code == 200
        body = resp.text
        assert "HTTP" in body
        assert "/admin/metrics/" in body  # back link

    def test_module_detail_unknown_slug_404(
        self, e2e_client: TestClient, e2e_auth_headers: dict[str, str]
    ) -> None:
        """
        Given an unregistered slug,
        When GET /admin/metrics/<unknown> is called as ADMIN,
        Then 404 is returned.
        """
        resp = e2e_client.get(
            "/admin/metrics/no-such-module", headers=e2e_auth_headers
        )
        assert resp.status_code == 404

    def test_module_detail_json_returns_sections(
        self, e2e_client: TestClient, e2e_auth_headers: dict[str, str]
    ) -> None:
        """
        Given a registered plugin slug,
        When GET /admin/metrics/api?module=http is called as ADMIN,
        Then JSON with sections array is returned.
        """
        resp = e2e_client.get(
            "/admin/metrics/api",
            params={"module": "http"},
            headers=e2e_auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] == "http"
        assert "sections" in body
