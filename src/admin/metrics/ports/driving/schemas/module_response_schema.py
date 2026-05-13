from msgspec import Struct


class ModuleKvResponse(Struct, frozen=True):
    label: str
    value: str
    severity: str


class ModuleSummaryResponse(Struct, frozen=True):
    slug: str
    name: str
    description: str
    kvs: tuple[ModuleKvResponse, ...]


class OverviewResponse(Struct, frozen=True):
    modules: tuple[ModuleSummaryResponse, ...]
    poll_interval_ms: int
