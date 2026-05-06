"""Validate RootConfig PROD invariants — AUTH_ADMIN_TOKEN required when APP_ENV=prod."""

import pytest

from root.config import RootConfig


def test_prod_without_admin_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("AUTH_ADMIN_TOKEN", raising=False)
    with pytest.raises(ValueError, match="AUTH_ADMIN_TOKEN must be set when APP_ENV=PROD"):
        RootConfig()


def test_prod_with_admin_token_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", "secret")
    config = RootConfig()
    assert config.app_env.value == "prod"


def test_dev_without_admin_token_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("AUTH_ADMIN_TOKEN", raising=False)
    config = RootConfig()
    assert config.app_env.value == "dev"
