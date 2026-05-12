"""Subclass of Litestar's PrometheusController, configured at app build.

Litestar's PrometheusController stores its `path` as a class attribute,
so we create a thin subclass at wire time with our config values baked
in. The subclass either inherits the open exposition behaviour (if
`prom_endpoint_public=True`) or applies the admin guard.
"""

from typing import Any

from litestar.plugins.prometheus import PrometheusController

from auth.ports.driving import require_role
from shared.domain.auth import Role

from ....config import MetricsConfig


def build_prom_controller(config: MetricsConfig) -> type[PrometheusController]:
    """Returns a PrometheusController subclass with path + guards set."""
    attrs: dict[str, Any] = {"path": config.prom_endpoint_path}
    if not config.prom_endpoint_public:
        attrs["guards"] = [require_role(Role.ADMIN)]
    return type("ConfiguredPromController", (PrometheusController,), attrs)
