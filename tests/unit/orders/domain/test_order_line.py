from decimal import Decimal

from orders.domain import Money, OrderLine


def test_subtotal_multiplies_unit_price_by_quantity() -> None:
    line = OrderLine(
        product_ref="sku-1", quantity=3, unit_price=Money(amount=Decimal("2.00"), currency="USD")
    )
    assert line.subtotal == Money(amount=Decimal("6.00"), currency="USD")
