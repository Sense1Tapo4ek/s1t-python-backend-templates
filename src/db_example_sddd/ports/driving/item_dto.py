from datetime import datetime
from typing import Annotated
from uuid import UUID

import msgspec
from litestar.dto import DTOConfig, MsgspecDTO

from ...domain import Item


class ItemModel(msgspec.Struct):
    id: UUID
    name: Annotated[str, msgspec.Meta(min_length=1, max_length=200)]
    description: str | None
    created_at: datetime


ItemReadDTO = MsgspecDTO[ItemModel]


class ItemWriteDTO(MsgspecDTO[ItemModel]):
    config = DTOConfig(exclude={"id", "created_at"})


class ItemPatchDTO(MsgspecDTO[ItemModel]):
    config = DTOConfig(exclude={"id", "created_at"}, partial=True)


def to_model(item: Item) -> ItemModel:
    return ItemModel(
        id=item.id, name=item.name, description=item.description, created_at=item.created_at
    )
