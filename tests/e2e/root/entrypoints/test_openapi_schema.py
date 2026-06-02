"""E2E: the OpenAPI schema is grouped and documented (no bare 'default')."""

_API_METHODS = {"get", "post", "patch", "put", "delete"}
_EXPECTED_TAGS = {
    "Health",
    "db_example (SDDD)",
    "db_example (Alchemy)",
    "Admin Logs",
    "Metrics",
    "Admin UI",
}


def _spec(e2e_client):
    resp = e2e_client.get("/schema/openapi.json")
    assert resp.status_code == 200
    return resp.json()


def test_tag_groups_declared(e2e_client) -> None:
    """Given the app, When fetching the OpenAPI spec, Then all tag groups are declared with descriptions."""
    spec = _spec(e2e_client)
    tags = {t["name"]: t for t in spec.get("tags", [])}
    assert set(tags) >= _EXPECTED_TAGS
    assert all(tags[name].get("description") for name in _EXPECTED_TAGS)


def test_every_operation_is_tagged(e2e_client) -> None:
    """Given the spec, When scanning every operation, Then none is left untagged (no 'default' bucket)."""
    spec = _spec(e2e_client)
    untagged = [
        f"{method.upper()} {path}"
        for path, ops in spec["paths"].items()
        for method, op in ops.items()
        if method in _API_METHODS and not op.get("tags")
    ]
    assert not untagged, f"untagged operations: {untagged}"


def test_top_level_metadata(e2e_client) -> None:
    """Given the spec, When reading info, Then a non-empty description is present."""
    spec = _spec(e2e_client)
    assert spec["info"].get("description")
