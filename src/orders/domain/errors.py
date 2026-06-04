from shared.generics.errors import DomainError


class EmptyOrder(DomainError):
    def __init__(self) -> None:
        super().__init__("order must have at least one line")


class NegativeMoney(DomainError):
    def __init__(self) -> None:
        super().__init__("money amount must not be negative")


class NonPositiveQuantity(DomainError):
    def __init__(self) -> None:
        super().__init__("order line quantity must be at least 1")


class CurrencyMismatch(DomainError):
    def __init__(self, expected: str, got: str) -> None:
        self.expected = expected
        self.got = got
        super().__init__(f"currency mismatch: expected {expected}, got {got}")
