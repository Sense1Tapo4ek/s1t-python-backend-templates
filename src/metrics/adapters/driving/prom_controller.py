from typing import Any

from litestar.plugins.prometheus import PrometheusController

from auth.ports.driving import require_role
from shared.domain.auth import Role

from ...config import MetricsConfig


def build_prom_controller(config: MetricsConfig) -> type[PrometheusController]:
    """Return a PrometheusController subclass with config values baked in.

    PrometheusController stores ``path`` as a class attribute, so a subclass
    is created at wire time. Guards are omitted when ``prom_endpoint_public``
    is True; otherwise the admin role is required.
    """
    attrs: dict[str, Any] = {"path": config.prom_endpoint_path}
    if not config.prom_endpoint_public:
        attrs["guards"] = [require_role(Role.ADMIN)]
    return type("ConfiguredPromController", (PrometheusController,), attrs)
