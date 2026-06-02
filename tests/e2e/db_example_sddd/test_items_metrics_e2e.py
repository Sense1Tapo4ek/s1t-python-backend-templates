"""E2E: creating an item emits the db_example counter visible at /metrics."""


def test_create_item_exposes_created_counter(e2e_client, e2e_auth_headers) -> None:
    """
    Given the warm e2e app,
    When an item is created then /metrics scraped with admin auth,
    Then the body contains both the create counter and the latency histogram.
    """
    created = e2e_client.post(
        "/db-example-sddd/pooled/items", json={"name": "metric-widget", "description": "d"}
    )
    assert created.status_code == 201

    scrape = e2e_client.get("/metrics", headers=e2e_auth_headers)
    assert scrape.status_code == 200
    assert "db_example_items_created_total" in scrape.text
    assert "db_example_item_create_seconds" in scrape.text
