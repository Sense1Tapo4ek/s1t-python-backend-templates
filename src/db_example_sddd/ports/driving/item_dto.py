from datetime import datetime
from typing import Annotated
from uuid import UUID

import msgspec
from litestar.dto import DTOConfig, MsgspecDTO

from ...domain import Item


class ItemModel(msgspec.Struct):
    id: Annotated[
        UUID,
        msgspec.Meta(
            description="Server-assigned identifier.",
            examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
        ),
    ]
    name: Annotated[
        str,
        msgspec.Meta(
            min_length=1,
            max_length=200,
            description="Human-readable item name.",
            examples=["widget"],
        ),
    ]
    description: Annotated[
        str | None,
        msgspec.Meta(
            description="Optional free-text description.",
            examples=["a small widget"],
        ),
    ]
    created_at: Annotated[
        datetime,
        msgspec.Meta(
            description="UTC creation timestamp (server clock).",
            examples=["2026-06-02T13:00:00+00:00"],
        ),
    ]


ItemReadDTO = MsgspecDTO[ItemModel]


class ItemWriteDTO(MsgspecDTO[ItemModel]):
    config = DTOConfig(exclude={"id", "created_at"})


class ItemPatchDTO(MsgspecDTO[ItemModel]):
    config = DTOConfig(exclude={"id", "created_at"}, partial=True)


def to_model(item: Item) -> ItemModel:
    return ItemModel(
        id=item.id, name=item.name, description=item.description, created_at=item.created_at
    )
