import json

_BASE = "/orders"
_BODY = {
    "customer_ref": "c-1",
    "currency": "USD",
    "lines": [{"product_ref": "sku-1", "quantity": 2, "unit_price": "5.00"}],
}


def test_place_and_list(e2e_client) -> None:
    """Given a valid order, When POST then GET, Then 201 with computed total and it lists."""
    r = e2e_client.post(_BASE, json=_BODY)
    assert r.status_code == 201
    body = r.json()
    assert body["customer_ref"] == "c-1"
    assert body["total"] == "10.00"
    assert body["status"] == "placed"
    assert len(body["lines"]) == 1

    r = e2e_client.get(_BASE, params={"limit": 10})
    assert r.status_code == 200
    orders = r.json()
    assert any(o["id"] == body["id"] for o in orders)


def test_empty_order_is_problem_json(e2e_client) -> None:
    """Given zero lines, When POSTing, Then 409 problem+json (EmptyOrder domain error)."""
    r = e2e_client.post(_BASE, json={"customer_ref": "c-1", "currency": "USD", "lines": []})
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/problem+json")


def test_live_feed_receives_placed_event(e2e_client) -> None:
    """Given an open SSE subscription, When an order is placed, Then the feed emits it."""
    with e2e_client.stream("GET", "/orders/feed") as feed:
        e2e_client.post(_BASE, json=_BODY)
        for line in feed.iter_lines():
            if line.startswith("data:"):
                payload = json.loads(line[len("data:"):].strip())
                assert payload["currency"] == "USD"
                break
