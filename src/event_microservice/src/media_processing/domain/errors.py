from shared.generics.errors import DomainError


class UnknownJobKind(DomainError):
    def __init__(self, value: str):
        self.value = value
        super().__init__(f"unknown job kind: {value}")
