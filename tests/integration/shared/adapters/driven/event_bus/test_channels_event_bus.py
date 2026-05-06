"""Integration tests for ChannelsEventBus over a real MemoryChannelsBackend."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend

from shared.adapters.driven.event_bus import ChannelsEventBus


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderPaidEvent:
    order_id: UUID
    amount: Decimal
    currency: str
    paid_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class UserSignedUpEvent:
    user_id: UUID
    email: str


@asynccontextmanager
async def _running_bus():
    """Run the ChannelsPlugin via its own async-context-manager so its pub/sub
    worker tasks are bound to the same loop as the test code. Going through
    AsyncTestClient runs the lifespan in a separate portal thread, which leaves
    `_pub_queue` stranded on a different loop and deadlocks `publish()`.
    """
    plugin = ChannelsPlugin(
        backend=MemoryChannelsBackend(),
        arbitrary_channels_allowed=True,
    )
    async with plugin:
        bus = ChannelsEventBus(_channels=plugin)
        try:
            yield bus
        finally:
            await bus.stop()


@pytest.mark.asyncio
class TestChannelsEventBusRoundtrip:
    async def test_handler_receives_typed_event(self) -> None:
        """
        Given a subscriber for OrderPaidEvent,
        When publish() is called,
        Then the handler receives the same value, fully typed (UUID/Decimal/datetime).
        """
        async with _running_bus() as bus:
            received: list[OrderPaidEvent] = []
            done = asyncio.Event()

            async def handler(ev: OrderPaidEvent) -> None:
                received.append(ev)
                done.set()

            bus.subscribe(OrderPaidEvent, handler)
            await bus.start()

            event = OrderPaidEvent(
                order_id=uuid4(),
                amount=Decimal("99.50"),
                currency="USD",
                paid_at=datetime.now(UTC),
            )
            await bus.publish(event)
            await asyncio.wait_for(done.wait(), timeout=2.0)

            assert received == [event]
            assert isinstance(received[0].order_id, UUID)
            assert isinstance(received[0].amount, Decimal)
            assert isinstance(received[0].paid_at, datetime)

    async def test_multiple_handlers_for_same_event_all_fire(self) -> None:
        async with _running_bus() as bus:
            a_calls: list[OrderPaidEvent] = []
            b_calls: list[OrderPaidEvent] = []
            latch = asyncio.Semaphore(0)

            async def a(ev: OrderPaidEvent) -> None:
                a_calls.append(ev)
                latch.release()

            async def b(ev: OrderPaidEvent) -> None:
                b_calls.append(ev)
                latch.release()

            bus.subscribe(OrderPaidEvent, a)
            bus.subscribe(OrderPaidEvent, b)
            await bus.start()

            event = OrderPaidEvent(
                order_id=uuid4(),
                amount=Decimal("1"),
                currency="USD",
                paid_at=datetime.now(UTC),
            )
            await bus.publish(event)
            for _ in range(2):
                await asyncio.wait_for(latch.acquire(), timeout=2.0)

            assert a_calls == [event]
            assert b_calls == [event]

    async def test_handlers_isolated_by_event_type(self) -> None:
        """A subscriber for OrderPaidEvent must not receive UserSignedUpEvent."""
        async with _running_bus() as bus:
            order_calls: list = []
            user_calls: list = []
            done = asyncio.Event()

            async def order_handler(ev: OrderPaidEvent) -> None:
                order_calls.append(ev)

            async def user_handler(ev: UserSignedUpEvent) -> None:
                user_calls.append(ev)
                done.set()

            bus.subscribe(OrderPaidEvent, order_handler)
            bus.subscribe(UserSignedUpEvent, user_handler)
            await bus.start()

            await bus.publish(UserSignedUpEvent(user_id=uuid4(), email="x@y"))
            await asyncio.wait_for(done.wait(), timeout=2.0)

            assert len(user_calls) == 1
            assert order_calls == []

    async def test_handler_exception_does_not_break_subsequent_events(self) -> None:
        """One bad handler must not freeze the worker for that event type."""
        async with _running_bus() as bus:
            seen: list[OrderPaidEvent] = []
            boom_first = True
            proceed = asyncio.Event()

            async def flaky(ev: OrderPaidEvent) -> None:
                nonlocal boom_first
                seen.append(ev)
                if boom_first:
                    boom_first = False
                    raise RuntimeError("first call fails")
                proceed.set()

            bus.subscribe(OrderPaidEvent, flaky)
            await bus.start()

            ev1 = OrderPaidEvent(
                order_id=uuid4(),
                amount=Decimal("1"),
                currency="USD",
                paid_at=datetime.now(UTC),
            )
            ev2 = OrderPaidEvent(
                order_id=uuid4(),
                amount=Decimal("2"),
                currency="USD",
                paid_at=datetime.now(UTC),
            )
            await bus.publish(ev1)
            await bus.publish(ev2)
            await asyncio.wait_for(proceed.wait(), timeout=2.0)

            assert len(seen) == 2  # both reached the handler

    async def test_subscribe_after_start_is_rejected(self) -> None:
        """Late subscribers would silently miss events already in flight."""
        async with _running_bus() as bus:
            async def handler(_ev: OrderPaidEvent) -> None: ...

            bus.subscribe(OrderPaidEvent, handler)
            await bus.start()

            with pytest.raises(RuntimeError, match="before start"):
                bus.subscribe(UserSignedUpEvent, handler)

    async def test_start_and_stop_are_idempotent(self) -> None:
        async with _running_bus() as bus:
            await bus.start()
            await bus.start()  # must not raise or duplicate workers
            await bus.stop()
            await bus.stop()
