import time
from typing import Any

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get

from ...ports.driving import MetricsFacade


class MetricsDemoController(Controller):
    path = "/metrics-demo"
    tags = ["Metrics"]  # noqa: RUF012

    @get(summary="Emit demo metrics")
    @inject
    async def emit(self, facade: FromDishka[MetricsFacade]) -> dict[str, Any]:
        """Teaching endpoint: exercise all three metric types via the facade.

        Unguarded on purpose -- it only mutates demo series. Delete this
        controller (and its route registration) when adapting the template.
        """
        start = time.perf_counter()
        facade.increment("widget_render_total")
        facade.set_gauge("widget_queue_depth", 3)
        facade.observe("widget_render_seconds", time.perf_counter() - start)
        return {"emitted": ["widget_render_total", "widget_queue_depth", "widget_render_seconds"]}
