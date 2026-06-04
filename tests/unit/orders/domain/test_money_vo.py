from decimal import Decimal

import pytest

from orders.domain import CurrencyMismatch, Money, NegativeMoney


class TestMoney:
    def test_add_same_currency(self) -> None:
        a = Money(amount=Decimal("1.00"), currency="USD")
        b = Money(amount=Decimal("2.50"), currency="USD")
        assert a.add(b) == Money(amount=Decimal("3.50"), currency="USD")

    def test_negative_amount_rejected(self) -> None:
        with pytest.raises(NegativeMoney):
            Money(amount=Decimal("-1"), currency="USD")

    def test_currency_mismatch_rejected(self) -> None:
        with pytest.raises(CurrencyMismatch):
            Money(amount=Decimal("1"), currency="USD").add(
                Money(amount=Decimal("1"), currency="EUR")
            )
