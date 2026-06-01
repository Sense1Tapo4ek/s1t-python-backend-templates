def test_author_crud_and_features(e2e_client) -> None:
    base = "/db-example-alchemy/authors"

    # bulk create
    r = e2e_client.post(f"{base}/bulk", json=[{"name": "Stephen King"}, {"name": "Jane Austen"}])
    assert r.status_code == 201

    # search + paginate (advanced repository features)
    r = e2e_client.get(base, params={"search": "king", "limit": 10, "offset": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    author_id = body["items"][0]["id"]

    # get with eager-loaded books relationship present
    r = e2e_client.get(f"{base}/{author_id}")
    assert r.status_code == 200
    assert "books" in r.json()

    # partial patch
    r = e2e_client.patch(f"{base}/{author_id}", json={"name": "Stephen Edwin King"})
    assert r.status_code == 200
    assert r.json()["name"] == "Stephen Edwin King"

    # delete + 404
    r = e2e_client.delete(f"{base}/{author_id}")
    assert r.status_code == 204
    r = e2e_client.get(f"{base}/{author_id}")
    assert r.status_code == 404
