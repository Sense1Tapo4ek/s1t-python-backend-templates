from dataclasses import dataclass

from .severity_vo import Severity


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricKvVo:
    label: str
    value: str
    severity: Severity
