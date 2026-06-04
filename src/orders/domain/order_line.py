from dataclasses import dataclass

from .money_vo import Money


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderLine:
    product_ref: str
    quantity: int
    unit_price: Money

    @property
    def subtotal(self) -> Money:
        return self.unit_price.scale(self.quantity)
