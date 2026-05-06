import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import msgspec
import structlog
from litestar.channels import ChannelsPlugin

_log = structlog.get_logger(__name__)


def _channel_name(event_type: type) -> str:
    return f"event:{event_type.__module__}.{event_type.__qualname__}"


@dataclass(slots=True, kw_only=True)
class _Subscription[E]:
    event_type: type[E]
    handler: Callable[[E], Awaitable[None]]
    task: asyncio.Task[None] | None = None
    ready: asyncio.Event = field(default_factory=asyncio.Event)


@dataclass(slots=True, kw_only=True)
class ChannelsEventBus:
    _channels: ChannelsPlugin
    # Heterogeneous: each entry is _Subscription[E_i] with a different E_i.
    # The unparameterised form is the honest spelling of an existential
    # generic — every API surface that touches a subscription rebinds E.
    _subscriptions: list[_Subscription] = field(default_factory=list)
    _started: bool = False

    async def publish(self, event: object) -> None:
        payload = msgspec.json.encode(event)
        self._channels.publish(payload, _channel_name(type(event)))

    def subscribe[E](
        self,
        event_type: type[E],
        handler: Callable[[E], Awaitable[None]],
    ) -> None:
        if self._started:
            raise RuntimeError(
                "subscribe() must be called before start(); the per-handler "
                "worker tasks are spun up at start time and registering later "
                "would silently drop events already in flight."
            )
        self._subscriptions.append(
            _Subscription(event_type=event_type, handler=handler),
        )

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        for sub in self._subscriptions:
            sub.task = asyncio.create_task(
                self._run(sub),
                name=f"event-bus:{sub.event_type.__name__}",
            )
        # Block until every worker has actually entered start_subscription().
        # Without this, a publish() that races a freshly-started bus drops
        # messages because no subscriber is registered with the backend yet.
        for sub in self._subscriptions:
            await sub.ready.wait()
        _log.info("event bus started", subscriber_count=len(self._subscriptions))

    async def stop(self) -> None:
        if not self._started:
            return
        tasks = [s.task for s in self._subscriptions if s.task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for sub in self._subscriptions:
            sub.task = None
        self._started = False
        _log.info("event bus stopped", subscriber_count=len(tasks))

    async def _run(self, sub: _Subscription) -> None:
        channel = _channel_name(sub.event_type)
        try:
            async with self._channels.start_subscription(channel) as subscriber:
                sub.ready.set()
                async for raw in subscriber.iter_events():
                    try:
                        event = msgspec.json.decode(raw, type=sub.event_type)
                    except msgspec.DecodeError:
                        # Skip malformed payloads instead of crashing the worker;
                        # likely a producer mismatch. Logged for diagnosis.
                        _log.warning(
                            "event decode failed",
                            channel=channel,
                            event_type=sub.event_type.__name__,
                            payload_preview=raw[:120],
                        )
                        continue
                    try:
                        await sub.handler(event)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        _log.exception(
                            "event handler failed",
                            event_type=sub.event_type.__name__,
                            handler=getattr(
                                sub.handler, "__qualname__", repr(sub.handler),
                            ),
                        )
        except asyncio.CancelledError:
            return
