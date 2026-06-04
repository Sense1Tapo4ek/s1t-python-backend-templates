from decimal import Decimal

import pytest

from orders.domain import Money, OrderLine
from orders.domain.errors import NonPositiveQuantity


def test_subtotal_multiplies_unit_price_by_quantity() -> None:
    line = OrderLine(
        product_ref="sku-1", quantity=3, unit_price=Money(amount=Decimal("2.00"), currency="USD")
    )
    assert line.subtotal == Money(amount=Decimal("6.00"), currency="USD")


@pytest.mark.parametrize("quantity", [0, -1])
def test_quantity_below_one_is_rejected(quantity: int) -> None:
    """Given a non-positive quantity, When building a line, Then NonPositiveQuantity."""
    with pytest.raises(NonPositiveQuantity):
        OrderLine(
            product_ref="sku-1",
            quantity=quantity,
            unit_price=Money(amount=Decimal("2.00"), currency="USD"),
        )
