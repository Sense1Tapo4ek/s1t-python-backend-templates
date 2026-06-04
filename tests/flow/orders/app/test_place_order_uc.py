from decimal import Decimal

import pytest
from tests.flow.orders.conftest import FakeClock, FakeRepo, FakeUoW, RecordingEventBus

from orders.app import PlaceOrderCommand, PlaceOrderUC
from orders.domain import Money, OrderLine, OrderPlacedEvent


def _cmd() -> PlaceOrderCommand:
    return PlaceOrderCommand(
        customer_ref="c-1",
        lines=[OrderLine(product_ref="sku-1", quantity=2, unit_price=Money(amount=Decimal("5.00"), currency="USD"))],
    )


@pytest.fixture
def uow() -> FakeUoW:
    return FakeUoW()


@pytest.fixture
def bus() -> RecordingEventBus:
    return RecordingEventBus()


@pytest.fixture
def uc(uow: FakeUoW, bus: RecordingEventBus) -> PlaceOrderUC:
    return PlaceOrderUC(_repo=FakeRepo(), _uow=uow, _event_bus=bus, _clock=FakeClock())


class TestPlaceOrder:
    @pytest.mark.asyncio
    async def test_saves_inside_uow_and_publishes_after_commit(
        self, uc: PlaceOrderUC, uow: FakeUoW, bus: RecordingEventBus
    ) -> None:
        """Given a command, When placed, Then it is saved in the UoW and one event published."""
        order = await uc(_cmd())
        assert uow.committed is True
        assert order.id in uc._repo.saved  # type: ignore[attr-defined]
        assert len(bus.published) == 1
        assert isinstance(bus.published[0], OrderPlacedEvent)

    @pytest.mark.asyncio
    async def test_no_events_published_if_uow_fails(self, bus: RecordingEventBus) -> None:
        """Given a UoW that raises, When placing, Then no event escapes (publish is post-commit)."""
        class FailingUoW(FakeUoW):
            async def __aenter__(self) -> "FailingUoW":
                raise RuntimeError("tx failed")

        uc = PlaceOrderUC(_repo=FakeRepo(), _uow=FailingUoW(), _event_bus=bus, _clock=FakeClock())
        with pytest.raises(RuntimeError):
            await uc(_cmd())
        assert bus.published == []
