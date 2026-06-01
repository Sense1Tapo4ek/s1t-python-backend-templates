from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from .errors import EmptyItemName


@dataclass(slots=True, kw_only=True)
class Item:
    id: UUID = field(default_factory=uuid4)
    name: str
    description: str | None
    created_at: datetime

    @classmethod
    def create(cls, *, name: str, description: str | None, created_at: datetime) -> "Item":
        if not name.strip():
            raise EmptyItemName()
        return cls(name=name, description=description, created_at=created_at)

    def update(self, *, name: str | None = None, description: str | None = None) -> None:
        if name is not None:
            if not name.strip():
                raise EmptyItemName()
            self.name = name
        if description is not None:
            self.description = description
