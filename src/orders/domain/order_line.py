from dataclasses import dataclass

from .errors import NonPositiveQuantity
from .money_vo import Money


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderLine:
    product_ref: str
    quantity: int
    unit_price: Money

    def __post_init__(self) -> None:
        if self.quantity < 1:
            raise NonPositiveQuantity()

    @property
    def subtotal(self) -> Money:
        return self.unit_price.scale(self.quantity)
