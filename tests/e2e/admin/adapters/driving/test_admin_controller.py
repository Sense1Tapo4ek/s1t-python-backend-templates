from litestar.status_codes import HTTP_200_OK
from litestar.testing import TestClient


def test_dashboard_renders_app_metadata(
    e2e_client: TestClient,
    e2e_auth_headers: dict[str, str],
) -> None:
    response = e2e_client.get("/admin/", headers=e2e_auth_headers)

    assert response.status_code == HTTP_200_OK
    body = response.text
    assert "test-service" in body
    assert "uptime" in body
    assert "started" in body


def test_logs_page_returns_html(
    e2e_client: TestClient,
    e2e_auth_headers: dict[str, str],
) -> None:
    response = e2e_client.get("/admin/logs", headers=e2e_auth_headers)

    assert response.status_code == HTTP_200_OK
    assert "text/html" in response.headers.get("content-type", "")
