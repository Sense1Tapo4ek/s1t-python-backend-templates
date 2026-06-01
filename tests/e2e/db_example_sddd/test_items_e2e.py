import pytest

PATHS = ["/db-example-sddd/pooled/items", "/db-example-sddd/per-request/items"]


@pytest.mark.parametrize("base", PATHS)
def test_crud_cycle(e2e_client, base: str) -> None:
    r = e2e_client.post(base, json={"name": "widget", "description": "d"})
    assert r.status_code == 201
    item = r.json()
    item_id = item["id"]
    assert item["name"] == "widget"

    r = e2e_client.get(f"{base}/{item_id}")
    assert r.status_code == 200

    r = e2e_client.get(base, params={"limit": 10, "offset": 0})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body

    # partial patch: only name; description preserved
    r = e2e_client.patch(f"{base}/{item_id}", json={"name": "renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "renamed"
    assert r.json()["description"] == "d"

    r = e2e_client.delete(f"{base}/{item_id}")
    assert r.status_code == 204

    r = e2e_client.get(f"{base}/{item_id}")
    assert r.status_code == 404


@pytest.mark.parametrize("base", PATHS)
def test_create_rejects_blank_name(e2e_client, base: str) -> None:
    r = e2e_client.post(base, json={"name": "", "description": None})
    assert r.status_code in (400, 422)
