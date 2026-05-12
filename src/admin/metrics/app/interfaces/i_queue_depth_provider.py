from typing import Protocol


class IQueueDepthProvider(Protocol):
    """Pull-based: current depth of the log queue this process owns.

    Implemented in the log subsystem (not admin/metrics). admin/metrics
    treats this as an optional input — None means "not applicable to
    this role" (e.g., the sink process doesn't have a producer queue).
    """

    def current_queue_depth(self) -> int: ...
    def total_dropped(self) -> int: ...
