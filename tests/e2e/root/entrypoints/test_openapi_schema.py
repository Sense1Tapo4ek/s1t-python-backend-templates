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


def test_api_operations_have_summary_or_description(e2e_client) -> None:
    """Given the spec, When scanning JSON-API operations, Then each (non Admin UI) has a summary or description."""
    spec = _spec(e2e_client)
    bare = []
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if method not in _API_METHODS:
                continue
            if "Admin UI" in (op.get("tags") or []):
                continue
            if not (op.get("summary") or op.get("description")):
                bare.append(f"{method.upper()} {path}")
    assert not bare, f"undocumented operations: {bare}"


def test_error_envelope_documented_on_item_lookup(e2e_client) -> None:
    """Given the spec, When reading the item-by-id GET, Then 404 is documented."""
    spec = _spec(e2e_client)
    # find the pooled items by-id path key (Litestar renders the param placeholder)
    key = next(p for p in spec["paths"] if p.startswith("/db-example-sddd/pooled/items/")
               and "{" in p and "get" in spec["paths"][p])
    assert "404" in spec["paths"][key]["get"]["responses"]
