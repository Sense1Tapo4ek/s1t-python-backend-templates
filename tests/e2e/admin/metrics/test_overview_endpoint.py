from litestar.testing import TestClient


class TestOverviewEndpoint:
    def test_overview_html_renders_cards(
        self, e2e_client: TestClient, e2e_auth_headers: dict[str, str]
    ) -> None:
        """
        Given the app started with admin/metrics provider,
        When GET /admin/metrics/ is called as ADMIN,
        Then HTML cards render with all 3 module names.
        """
        resp = e2e_client.get("/admin/metrics/", headers=e2e_auth_headers)
        assert resp.status_code == 200
        body = resp.text
        assert "HTTP" in body
        assert "Logs" in body
        assert "Workers" in body

    def test_overview_json_endpoint(
        self, e2e_client: TestClient, e2e_auth_headers: dict[str, str]
    ) -> None:
        """
        Given the app started with admin/metrics provider,
        When GET /admin/metrics/api?module=overview is called as ADMIN,
        Then JSON with modules list is returned.
        """
        resp = e2e_client.get(
            "/admin/metrics/api",
            params={"module": "overview"},
            headers=e2e_auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "modules" in body
        slugs = {m["slug"] for m in body["modules"]}
        assert {"http", "logs", "workers"}.issubset(slugs)

    def test_overview_requires_admin(self, e2e_client: TestClient) -> None:
        """
        Given no auth headers,
        When GET /admin/metrics/ is called,
        Then 401, 403, or a redirect is returned.
        """
        resp = e2e_client.get("/admin/metrics/", follow_redirects=False)
        assert resp.status_code in (401, 403, 302, 303)
