from shared.generics.errors import DomainError


class MalformedLogLine(DomainError):
    def __init__(self, *, preview: str) -> None:
        self.preview = preview
        super().__init__(f"malformed log line: {preview!r}")
