import importlib

import pytest

from admin.log.ports.errors import LogReadError
from shared.generics.errors import PortError


class TestErrorTaxonomy:
    def test_log_read_error_is_port_error(self) -> None:
        """
        Given LogReadError,
        When checking its base,
        Then it is a PortError (routes to 503 via the global handler).
        """
        assert issubclass(LogReadError, PortError)

    def test_dsl_handlers_module_gone(self) -> None:
        """
        Given DSL removal,
        When importing the old handler module,
        Then ModuleNotFoundError.
        """
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("admin.log.adapters.driving.error_handlers")
