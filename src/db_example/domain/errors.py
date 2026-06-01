from shared.generics.errors import DomainError


class EmptyItemName(DomainError):
    def __init__(self) -> None:
        super().__init__("item name must not be empty")
