"""Validate RootConfig PROD invariants -- admin token + CSRF secret required."""

import pytest

from root.config import RootConfig


def test_prod_without_admin_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("AUTH_ADMIN_TOKEN", raising=False)
    with pytest.raises(ValueError, match="AUTH_ADMIN_TOKEN must be set when APP_ENV=prod"):
        RootConfig()


def test_prod_without_csrf_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", "secret")
    monkeypatch.delenv("CSRF_SECRET", raising=False)
    with pytest.raises(ValueError, match="CSRF_SECRET must be set when APP_ENV=prod"):
        RootConfig()


def test_prod_with_required_secrets_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", "secret")
    monkeypatch.setenv("CSRF_SECRET", "csrf-signing-secret")
    config = RootConfig()
    assert config.app_env.value == "prod"


def test_dev_without_secrets_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("AUTH_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("CSRF_SECRET", raising=False)
    config = RootConfig()
    assert config.app_env.value == "dev"
