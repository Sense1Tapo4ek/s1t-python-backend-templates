class FeedLimiter:
    """Per-process cap on concurrent SSE subscribers.

    Single instance per worker (APP scope). Safe without locks: handlers run
    on one event loop and both methods are synchronous.
    """

    def __init__(self, max_connections: int) -> None:
        self._max = max_connections
        self._active = 0

    def try_acquire(self) -> bool:
        if self._active >= self._max:
            return False
        self._active += 1
        return True

    def release(self) -> None:
        self._active = max(0, self._active - 1)
