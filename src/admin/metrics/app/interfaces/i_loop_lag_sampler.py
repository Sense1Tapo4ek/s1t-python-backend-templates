from typing import Protocol


class ILoopLagSampler(Protocol):
    """Continuously samples event loop scheduling latency.

    The sampler runs a long-lived background task (started via start()),
    holds the last N measurements, and exposes the rolling p95 in
    milliseconds via current_p95_ms().
    """

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def current_p95_ms(self) -> float: ...
