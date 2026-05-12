"""Simple registry: holds the plugins collected via Dishka multi-provide.

App scope — one instance per process, built once at DI startup. Rejects
duplicate or reserved slugs at construction time; this is a wiring
error, not a runtime condition.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from ....app.interfaces import IMetricsModulePlugin
from ....domain import DuplicateSlugError

_RESERVED_SLUGS = frozenset({"overview", "api"})


@dataclass(slots=True, kw_only=True)
class InMemoryModulePluginRegistry:
    _plugins: tuple[IMetricsModulePlugin, ...]

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for p in self._plugins:
            if p.slug in _RESERVED_SLUGS:
                raise ValueError(
                    f"slug {p.slug!r} is reserved and cannot be used"
                )
            if p.slug in seen:
                raise DuplicateSlugError(p.slug)
            seen.add(p.slug)

    def all(self) -> Sequence[IMetricsModulePlugin]:
        return self._plugins

    def find(self, slug: str) -> IMetricsModulePlugin | None:
        return next((p for p in self._plugins if p.slug == slug), None)
