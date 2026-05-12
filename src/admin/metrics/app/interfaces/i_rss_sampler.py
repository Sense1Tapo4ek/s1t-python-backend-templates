from typing import Protocol


class IRssSampler(Protocol):
    """Pull-based: resident memory in bytes, sampled on demand."""

    def current_rss_bytes(self) -> int: ...
