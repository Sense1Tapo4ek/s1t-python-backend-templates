from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, delete, get, patch, post
from litestar.dto import DTOData
from litestar.pagination import OffsetPagination
from litestar.params import Parameter
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from ....ports.driving import (
    ItemModel,
    ItemPatchDTO,
    ItemReadDTO,
    ItemWriteDTO,
    PooledItemFacade,
)


class PooledItemController(Controller):
    path = "/db-example-sddd/pooled/items"
    return_dto = ItemReadDTO

    @post("/", dto=ItemWriteDTO, status_code=HTTP_201_CREATED)
    @inject
    async def create(self, data: DTOData[ItemModel], facade: FromDishka[PooledItemFacade]) -> ItemModel:
        return await facade.create(**data.as_builtins())

    @get("/")
    @inject
    async def list_items(
        self,
        facade: FromDishka[PooledItemFacade],
        limit: Annotated[int, Parameter(ge=1, le=200)] = 50,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[ItemModel]:
        items, total = await facade.list(limit, offset)
        return OffsetPagination(items=items, total=total, limit=limit, offset=offset)

    @get("/{item_id:uuid}")
    @inject
    async def get_one(self, item_id: UUID, facade: FromDishka[PooledItemFacade]) -> ItemModel:
        return await facade.get(item_id)

    @patch("/{item_id:uuid}", dto=ItemPatchDTO)
    @inject
    async def update(self, item_id: UUID, data: DTOData[ItemModel],
                    facade: FromDishka[PooledItemFacade]) -> ItemModel:
        return await facade.update(item_id, **data.as_builtins())

    @delete("/{item_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    @inject
    async def remove(self, item_id: UUID, facade: FromDishka[PooledItemFacade]) -> None:
        await facade.delete(item_id)
