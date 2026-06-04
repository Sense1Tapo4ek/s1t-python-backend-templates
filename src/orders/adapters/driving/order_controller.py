from typing import Annotated

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get, post
from litestar.params import Parameter
from litestar.status_codes import HTTP_201_CREATED

from shared.adapters.openapi import error_responses

from ...ports.driving import OrderModel, OrderReadDTO, OrdersFacade, PlaceOrderRequest


class OrderController(Controller):
    path = "/orders"
    tags = ["orders (realtime)"]  # noqa: RUF012
    return_dto = OrderReadDTO

    @post("/", status_code=HTTP_201_CREATED, summary="Place an order",
          responses=error_responses(400, 409, 503))
    @inject
    async def place(self, data: PlaceOrderRequest, facade: FromDishka[OrdersFacade]) -> OrderModel:
        """Place an order; emits OrderPlaced (in-process bus + live feed)."""
        return await facade.place(data)

    @get("/", summary="List recent orders", responses=error_responses(503))
    @inject
    async def list_recent(
        self,
        facade: FromDishka[OrdersFacade],
        limit: Annotated[int, Parameter(ge=1, le=200)] = 50,
    ) -> list[OrderModel]:
        """Return the most recent orders (newest first)."""
        return await facade.list_recent(limit)
