from polyfactory.factories import DataclassFactory

from orders.domain import Order


class OrderFactory(DataclassFactory[Order]):
    pass
