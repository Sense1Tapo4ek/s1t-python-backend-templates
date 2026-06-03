import pytest


def test_schema_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given no overrides, When constructing, Then schema_name defaults to the context."""
    monkeypatch.setenv("APP_NAME", "x")
    from db_example_litestar.config import DbExampleLitestarConfig

    cfg = DbExampleLitestarConfig()
    assert cfg.schema_name == "db_example_litestar"
