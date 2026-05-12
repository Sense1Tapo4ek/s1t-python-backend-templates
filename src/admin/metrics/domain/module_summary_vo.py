from dataclasses import dataclass

from .metric_kv_vo import MetricKvVo


@dataclass(frozen=True, slots=True, kw_only=True)
class ModuleSummaryVo:
    slug: str
    name: str
    kvs: tuple[MetricKvVo, ...]

    def __post_init__(self) -> None:
        if not self.kvs:
            raise ValueError("summary must contain at least one KV")
