from dataclasses import dataclass
from datetime import datetime

from .dsl_constants import KV_KEY_PATTERN, VALID_LEVELS
from .errors import InvalidLogFilterError


@dataclass(frozen=True, slots=True, kw_only=True)
class LogFilterVo:
    """Immutable filter spec produced by the DSL parser.

    Semantics:
    - `min_level` uses level rank, not equality (`WARN` matches WARN /
      ERROR / CRITICAL).
    - `levels`, when set, takes precedence over `min_level` and matches
      exactly (OR-combined).
    - `loggers` are glob patterns: `auth` matches exactly; `auth.*`
      matches descendants only (`auth.x`, `auth.x.y`), never `auth`.
    """

    min_level: str | None = None
    levels: tuple[str, ...] | None = None
    loggers: tuple[str, ...] | None = None
    trace_id: str | None = None
    kv_filters: tuple[tuple[str, str], ...] | None = None
    time_from: datetime | None = None
    time_to: datetime | None = None
    fts_phrase: str | None = None
    live_mode: bool = False

    def __post_init__(self) -> None:
        if self.min_level is not None and self.min_level.upper() not in VALID_LEVELS:
            raise InvalidLogFilterError(
                field="min_level",
                reason=f"unknown level {self.min_level!r}",
            )
        if self.levels is not None:
            if len(self.levels) == 0:
                raise InvalidLogFilterError(
                    field="levels",
                    reason="levels must not be empty when set",
                )
            for lvl in self.levels:
                if lvl.upper() not in VALID_LEVELS:
                    raise InvalidLogFilterError(
                        field="levels",
                        reason=f"unknown level {lvl!r}",
                    )
        if self.min_level is not None and self.levels is not None:
            raise InvalidLogFilterError(
                field="levels",
                reason="levels and min_level are mutually exclusive",
            )
        if self.loggers is not None:
            for pattern in self.loggers:
                if pattern.endswith(".*") and len(pattern) <= 2:
                    raise InvalidLogFilterError(
                        field="loggers",
                        reason="glob requires non-empty prefix",
                    )
        if self.kv_filters is not None:
            for key, _value in self.kv_filters:
                if not KV_KEY_PATTERN.fullmatch(key):
                    raise InvalidLogFilterError(
                        field="kv_filters",
                        reason=f"invalid kv key {key!r}",
                    )
        if (
            self.time_from is not None
            and self.time_to is not None
            and self.time_from > self.time_to
        ):
            raise InvalidLogFilterError(
                field="time_to",
                reason="time_to must be >= time_from",
            )

    @classmethod
    def empty(cls) -> "LogFilterVo":
        return cls()
