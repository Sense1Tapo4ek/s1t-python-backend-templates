import os

import pytest

from shared.generics import config as generic_config_module


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests independent from the developer's local .env file."""

    monkeypatch.setattr(generic_config_module, "_resolve_env_file", lambda: None)
    monkeypatch.setenv("SNITCHBOT_DISABLED", "1")
    for env_var in (
        "SNITCHBOT_TOKEN",
        "SNITCHBOT_CHAT_ID",
        "APP_NAME",
        "APP_ENV",
        "APP_HOST",
        "APP_PORT",
        "APP_WORKERS",
        "VOLUME_PATH",
        "RUNTIME_PATH",
        "AUTH_ADMIN_TOKEN",
    ):
        monkeypatch.delenv(env_var, raising=False)
    yield
    os.environ.pop("SNITCHBOT_DISABLED", None)
