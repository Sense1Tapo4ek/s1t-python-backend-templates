from shared.generics.errors import PortError


class LogReadError(PortError):
    def __init__(self, *, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"cannot read log file {path}: {reason}")
