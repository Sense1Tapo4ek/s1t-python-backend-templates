from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerIdVo:
    host: str
    pid: int

    def __post_init__(self) -> None:
        if not self.host:
            raise ValueError("host must be non-empty")
        if self.pid <= 0:
            raise ValueError("pid must be positive")

    def __str__(self) -> str:
        return f"{self.host}:{self.pid}"

    @classmethod
    def parse(cls, raw: str) -> "WorkerIdVo":
        host, sep, pid_str = raw.partition(":")
        if not sep:
            raise ValueError(f"invalid worker id: {raw!r}")
        try:
            pid = int(pid_str)
        except ValueError as exc:
            raise ValueError(f"invalid pid in {raw!r}") from exc
        return cls(host=host, pid=pid)
