from polyfactory.factories import DataclassFactory

from db_example_sddd.domain import Item


class ItemFactory(DataclassFactory[Item]):
    pass
