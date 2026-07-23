import pytest


@pytest.mark.asyncio
class TestLogReadEndpoints:
    async def test_index_renders_template(self, e2e_client, e2e_auth_headers) -> None:
        """
        Given an admin user,
        When GET /admin/logs/,
        Then the log UI HTML is returned.
        """
        resp = e2e_client.get("/admin/logs/", headers=e2e_auth_headers)
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    async def test_tail_page_returns_entries_and_cursor(self, e2e_client, e2e_auth_headers) -> None:
        """
        Given a populated log file,
        When GET /api/v1/admin/logs/,
        Then a JSON page with entries and a cursor is returned.
        """
        resp = e2e_client.get("/api/v1/admin/logs/", headers=e2e_auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "entries" in body
        assert "cursor" in body

    async def test_older_rejects_bad_cursor(self, e2e_client, e2e_auth_headers) -> None:
        """
        Given a malformed cursor,
        When GET /api/v1/admin/logs/older?cursor=!!!,
        Then 400 is returned (validation, not 500).
        """
        resp = e2e_client.get("/api/v1/admin/logs/older?cursor=%21%21%21", headers=e2e_auth_headers)
        assert resp.status_code == 400

    async def test_clear_endpoint_is_gone(self, e2e_client, e2e_auth_headers) -> None:
        """
        Given the simplified controller,
        When DELETE /api/v1/admin/logs/,
        Then 405 Method Not Allowed.
        """
        resp = e2e_client.delete("/api/v1/admin/logs/", headers=e2e_auth_headers)
        assert resp.status_code == 405


@pytest.mark.asyncio
class TestExportEndpoint:
    async def test_ndjson_export(self, e2e_client, e2e_auth_headers) -> None:
        """
        Given an admin user,
        When GET /api/v1/admin/logs/export/?format=ndjson,
        Then a downloadable NDJSON stream is returned.
        """
        resp = e2e_client.get("/api/v1/admin/logs/export/?format=ndjson", headers=e2e_auth_headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/x-ndjson")
        assert "attachment" in resp.headers["content-disposition"]

    async def test_unknown_format_rejected(self, e2e_client, e2e_auth_headers) -> None:
        """
        Given an unsupported format,
        When GET .../export/?format=xml,
        Then 400 is returned.
        """
        resp = e2e_client.get("/api/v1/admin/logs/export/?format=xml", headers=e2e_auth_headers)
        assert resp.status_code == 400


def test_admin_api_401_is_problem_json(e2e_client) -> None:
    """Given no token, When calling the admin logs API, Then 401 problem+json."""
    resp = e2e_client.get("/api/v1/admin/logs/", headers={"accept": "application/json"})
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["type"] == "urn:litestar-base:error:unauthorized"


def test_admin_browser_401_redirects_to_login(e2e_client) -> None:
    """Given a browser with no cookie, When GETting /admin, Then 303 to login."""
    resp = e2e_client.get("/admin", headers={"accept": "text/html"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/admin/login")
