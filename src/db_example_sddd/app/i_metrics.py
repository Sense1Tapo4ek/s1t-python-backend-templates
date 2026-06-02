from typing import Protocol


class IMetrics(Protocol):
    """Subset of the metrics context's facade this context consumes.

    Duplicated (not imported) per S-DDD cross-context rules; the ACL in
    ports/driven/acl/ adapts the real metrics facade to this protocol.
    """

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None: ...
    def observe(self, name: str, value: float, **labels: str) -> None: ...
