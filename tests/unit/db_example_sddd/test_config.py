import pytest
from pydantic import ValidationError


def test_schema_and_pool_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given no overrides, When constructing, Then schema + pool defaults apply."""
    monkeypatch.setenv("APP_NAME", "x")
    from db_example_sddd.config import DbExampleSdddConfig

    cfg = DbExampleSdddConfig()
    assert cfg.schema_name == "db_example_sddd"
    assert cfg.pool_size == 4


def test_pool_size_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given an out-of-range pool size, When constructing, Then validation fails."""
    monkeypatch.setenv("APP_NAME", "x")
    monkeypatch.setenv("DB_EXAMPLE_SDDD_POOL_SIZE", "999")
    from db_example_sddd.config import DbExampleSdddConfig

    with pytest.raises(ValidationError):
        DbExampleSdddConfig()
