from shared.generics.errors import DomainError


class EmptySourceKey(DomainError):
    def __init__(self) -> None:
        super().__init__("video source_key must not be empty")


class InvalidTransition(DomainError):
    def __init__(self, frm: str, to: str) -> None:
        self.frm = frm
        self.to = to
        super().__init__(f"invalid status transition: {frm} -> {to}")
