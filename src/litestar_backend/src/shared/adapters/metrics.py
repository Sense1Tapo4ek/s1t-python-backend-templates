import glob
import os
from typing import Any

from litestar.plugins.prometheus import PrometheusController

from auth.ports.driving import require_role
from shared.config import MetricsConfig
from shared.domain.auth import Role


def build_prom_controller(config: MetricsConfig) -> type[PrometheusController]:
    """Return a PrometheusController subclass with config values baked in.

    PrometheusController stores ``path`` as a class attribute, so a subclass
    is created at wire time. Guards are omitted when ``prom_endpoint_public``
    is True; otherwise the admin role is required.
    """
    attrs: dict[str, Any] = {"path": config.prom_endpoint_path, "tags": ["Metrics"]}
    if not config.prom_endpoint_public:
        attrs["guards"] = [require_role(Role.ADMIN)]
    return type("ConfiguredPromController", (PrometheusController,), attrs)


def bootstrap_multiproc(config: MetricsConfig) -> None:
    """Materialize the prometheus multiprocess dir and wipe stale shards.

    Must be called before uvicorn forks workers so every worker inherits
    PROMETHEUS_MULTIPROC_DIR. Raises RuntimeError when multiproc_dir is
    None (the MetricsConfig validator always resolves it; this path
    indicates a mis-wired config).
    """
    multiproc_dir = config.multiproc_dir
    if multiproc_dir is None:
        raise RuntimeError("MetricsConfig failed to resolve multiproc_dir")
    os.makedirs(multiproc_dir, exist_ok=True)
    for stale in glob.glob(str(multiproc_dir / "*.db")):
        os.remove(stale)
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(multiproc_dir)


def mark_dead() -> None:
    """Call prometheus_client mark_process_dead for this PID on shutdown.

    No-op when multiprocess mode is inactive (e.g. single-worker or test).
    """
    try:
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(os.getpid())
    except Exception:
        pass
