from shared.generics.errors import DomainError


class DslSyntaxError(DomainError):
    def __init__(self, *, position: int, reason: str) -> None:
        self.position = position
        self.reason = reason
        super().__init__(f"DSL syntax error at position {position}: {reason}")


class InvalidLogFilterError(DomainError):
    """LogFilterVo invariant violation. Raised by LogFilterVo.__post_init__."""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"invalid LogFilterVo.{field}: {reason}")
