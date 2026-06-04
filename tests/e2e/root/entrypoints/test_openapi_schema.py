"""E2E: the OpenAPI schema is grouped and documented (no bare 'default')."""

from auth.config import ADMIN_COOKIE_NAME

_API_METHODS = {"get", "post", "patch", "put", "delete"}
_EXPECTED_TAGS = {
    "Health",
    "media",
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


def _author_by_id_key(spec) -> str:
    # find the authors by-id path key (Litestar renders the param placeholder)
    return next(p for p in spec["paths"] if p.startswith("/db-example-litestar/authors/")
                and "{" in p and "get" in spec["paths"][p])


def test_error_envelope_documented_on_author_lookup(e2e_client) -> None:
    """Given the spec, When reading the author-by-id GET, Then 404 is documented."""
    spec = _spec(e2e_client)
    assert "404" in spec["paths"][_author_by_id_key(spec)]["get"]["responses"]


def test_error_response_advertises_problem_details(e2e_client) -> None:
    """Given the spec, When reading the author 404 response, Then it serves the RFC 9457 problem+json schema."""
    spec = _spec(e2e_client)
    resp = spec["paths"][_author_by_id_key(spec)]["get"]["responses"]["404"]
    content = resp["content"]
    assert "application/problem+json" in content, list(content)
    ref = content["application/problem+json"]["schema"]["$ref"]
    schema_name = ref.rsplit("/", 1)[-1]
    props = spec["components"]["schemas"][schema_name]["properties"]
    assert {"type", "title", "status"} <= set(props)


def test_video_schema_has_field_examples_and_descriptions(e2e_client) -> None:
    """Given the spec, When reading the VideoModel schema, Then source_key carries a description and an example."""
    spec = _spec(e2e_client)
    schemas = spec["components"]["schemas"]
    # MsgspecDTO derives per-operation schemas (e.g. "UploadVideoModelResponseBody"),
    # not a bare "VideoModel"; the exact key is auto-suffixed on collision. Scan
    # for any DTO-derived VideoModel schema exposing the `source_key` property.
    source_key = next(
        props["source_key"]
        for k, v in schemas.items()
        if "VideoModel" in k and "source_key" in (props := v.get("properties", {}))
    )
    assert source_key.get("description")
    assert source_key.get("examples") or source_key.get("example")


def test_security_schemes_declared(e2e_client) -> None:
    """Given the spec, When reading components, Then bearer + adminCookie schemes exist."""
    spec = _spec(e2e_client)
    schemes = spec.get("components", {}).get("securitySchemes", {})
    assert schemes.get("bearer") == {"type": "http", "scheme": "bearer"}
    assert schemes.get("adminCookie", {}).get("type") == "apiKey"
    assert schemes["adminCookie"]["in"] == "cookie"
    assert schemes["adminCookie"]["name"] == ADMIN_COOKIE_NAME


_EXPECTED_PROTECTED_PATHS = {
    "/admin",
    "/admin/logs",
    "/api/v1/admin/logs",
    "/api/v1/admin/logs/export",
    "/api/v1/admin/logs/older",
    "/api/v1/admin/logs/stream",
}


def test_protected_operations_declare_security(e2e_client) -> None:
    """Given the spec, When scanning operations, Then all known protected paths require security."""
    spec = _spec(e2e_client)
    secured_paths = {
        p
        for p, ops in spec["paths"].items()
        for m, op in ops.items()
        if m in _API_METHODS and op.get("security")
    }
    missing = _EXPECTED_PROTECTED_PATHS - secured_paths
    assert not missing, f"missing security on: {missing}"
