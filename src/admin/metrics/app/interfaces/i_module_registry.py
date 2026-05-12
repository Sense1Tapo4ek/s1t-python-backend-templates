from collections.abc import Sequence
from typing import Protocol

from .i_module_plugin import IMetricsModulePlugin


class IModulePluginRegistry(Protocol):
    def all(self) -> Sequence[IMetricsModulePlugin]: ...

    def find(self, slug: str) -> IMetricsModulePlugin | None: ...
