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


_BASE = "/db-example-sddd/pooled/items"


def test_domain_error_is_problem_json(e2e_client) -> None:
    """Given a whitespace name, When POSTing, Then 409 problem+json with domain detail."""
    # "   " passes the DTO's min_length=1 but fails Item.create's name.strip()
    # -> EmptyItemName (DomainError) -> 409.
    resp = e2e_client.post(_BASE, json={"name": "   ", "description": None})
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 409
    assert body["type"].startswith("urn:litestar-base:error:")
    assert body["detail"]
    assert body["instance"] == _BASE


def test_not_found_is_problem_json(e2e_client) -> None:
    """Given a missing id, When GETting, Then a 404 problem+json."""
    resp = e2e_client.get(f"{_BASE}/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["status"] == 404


def test_validation_error_is_problem_json_with_field_detail(e2e_client) -> None:
    """Given a body missing `name`, When POSTing, Then 4xx problem+json keeping field detail."""
    resp = e2e_client.post(_BASE, json={"description": "no name field"})
    assert resp.status_code in (400, 422)
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    # MsgspecDTO decode failures raise SerializationException, which carries no
    # Litestar `extra`; the field-level message lives in `title` instead.
    assert "name" in body["title"]
