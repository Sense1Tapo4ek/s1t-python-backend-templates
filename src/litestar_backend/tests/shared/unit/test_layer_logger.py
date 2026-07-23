from structlog.testing import capture_logs

from shared.logging import Layer, layer_logger


def test_layer_logger_binds_app_layer() -> None:
    """layer_logger(Layer.APP, ...) tags every record with layer="app"."""
    with capture_logs() as logs:
        layer_logger(Layer.APP, "X").info("e")
    assert logs[0]["layer"] == "app"


def test_layer_logger_binds_adapters_driving_layer() -> None:
    """The enum value is emitted verbatim as the layer field."""
    with capture_logs() as logs:
        layer_logger(Layer.ADAPTERS_DRIVING, "Y").info("e")
    assert logs[0]["layer"] == "adapters_driving"


def test_layer_enum_has_no_domain_member() -> None:
    """Domain never logs, so Layer intentionally omits a DOMAIN member."""
    assert not hasattr(Layer, "DOMAIN")
