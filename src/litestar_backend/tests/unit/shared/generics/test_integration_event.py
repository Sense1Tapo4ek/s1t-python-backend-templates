from datetime import UTC, datetime
from uuid import uuid4

import msgspec

from shared.generics.integration_event import IntegrationEvent


class _OrderShipped(IntegrationEvent, frozen=True, kw_only=True):
    event_type: str = "order_shipped"
    order_ref: str


def test_envelope_fields_ride_along_with_the_payload() -> None:
    """
    Given a subclass adding payload fields,
    When it is JSON-encoded,
    Then envelope fields (event_id, occurred_at, version) and payload fields
    are all present in one flat object.
    """
    # Arrange
    event_id = uuid4()
    occurred_at = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    event = _OrderShipped(event_id=event_id, occurred_at=occurred_at, order_ref="ord-1")

    # Act
    decoded = msgspec.json.decode(msgspec.json.encode(event))

    # Assert
    assert decoded["event_id"] == str(event_id)
    assert decoded["version"] == 1
    assert decoded["event_type"] == "order_shipped"
    assert decoded["order_ref"] == "ord-1"
    assert decoded["occurred_at"].startswith("2026-07-20T12:00:00")


def test_round_trip_preserves_identity() -> None:
    """
    Given an encoded event,
    When decoded back into the subclass type,
    Then the struct round-trips exactly (frozen value semantics).
    """
    # Arrange
    event = _OrderShipped(event_id=uuid4(), occurred_at=datetime.now(tz=UTC), order_ref="ord-2")

    # Act
    back = msgspec.json.decode(msgspec.json.encode(event), type=_OrderShipped)

    # Assert
    assert back == event
