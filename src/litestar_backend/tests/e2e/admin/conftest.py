import pytest

from _e2e_constants import E2E_ADMIN_TOKEN


@pytest.fixture(autouse=True)
def _set_admin_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {E2E_ADMIN_TOKEN}"}
