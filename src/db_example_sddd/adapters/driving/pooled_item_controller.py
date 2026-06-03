from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, delete, get, patch, post
from litestar.dto import DTOData
from litestar.pagination import OffsetPagination
from litestar.params import Parameter
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from shared.adapters.openapi import error_responses

from ...ports.driving import (
    ItemModel,
    ItemPatchDTO,
    ItemReadDTO,
    ItemWriteDTO,
    PooledItemFacade,
)


class PooledItemController(Controller):
    path = "/db-example-sddd/pooled/items"
    tags = ["db_example (SDDD)"]  # noqa: RUF012
    return_dto = ItemReadDTO

    @post("/", dto=ItemWriteDTO, status_code=HTTP_201_CREATED,
          summary="Create an item", responses=error_responses(400, 409, 503))
    @inject
    async def create(self, data: DTOData[ItemModel], facade: FromDishka[PooledItemFacade]) -> ItemModel:
        """Create an item via the pooled (shared-connection) facade.

        Emits the ``db_example_items_created_total`` counter (see Metrics).
        """
        return await facade.create(**data.as_builtins())

    @get("/", summary="List items (paginated)", responses=error_responses(503))
    @inject
    async def list_items(
        self,
        facade: FromDishka[PooledItemFacade],
        limit: Annotated[int, Parameter(ge=1, le=200)] = 50,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[ItemModel]:
        """Return a page of items with the total count for offset pagination."""
        items, total = await facade.list(limit, offset)
        return OffsetPagination(items=items, total=total, limit=limit, offset=offset)

    @get("/{item_id:uuid}", summary="Get an item by id", responses=error_responses(404, 503))
    @inject
    async def get_one(self, item_id: UUID, facade: FromDishka[PooledItemFacade]) -> ItemModel:
        """Fetch a single item by id."""
        return await facade.get(item_id)

    @patch("/{item_id:uuid}", dto=ItemPatchDTO,
           summary="Update an item", responses=error_responses(400, 404, 409, 503))
    @inject
    async def update(self, item_id: UUID, data: DTOData[ItemModel],
                    facade: FromDishka[PooledItemFacade]) -> ItemModel:
        """Partially update an item by id."""
        return await facade.update(item_id, **data.as_builtins())

    @delete("/{item_id:uuid}", status_code=HTTP_204_NO_CONTENT,
            summary="Delete an item", responses=error_responses(404, 503))
    @inject
    async def remove(self, item_id: UUID, facade: FromDishka[PooledItemFacade]) -> None:
        """Delete an item by id."""
        await facade.delete(item_id)
