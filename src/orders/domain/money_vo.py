from dataclasses import dataclass
from decimal import Decimal

from .errors import CurrencyMismatch, NegativeMoney


@dataclass(frozen=True, slots=True, kw_only=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise NegativeMoney()

    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise CurrencyMismatch(self.currency, other.currency)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def scale(self, factor: int) -> "Money":
        return Money(amount=self.amount * factor, currency=self.currency)
