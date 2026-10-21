from conftest import USER_B


def _swipe(api, product_id, kind="like"):
    assert api.client.post("/v1/interactions", json={"product_id": product_id, "type": kind}).status_code == 201


def _wardrobe_ids(api):
    return [p["id"] for p in api.client.get("/v1/wardrobe").json()["items"]]


def test_every_like_is_in_the_wardrobe_newest_first(api, ids):
    _swipe(api, ids["jeans"])
    _swipe(api, ids["dress"], "dislike")
    _swipe(api, ids["heels"])

    body = api.client.get("/v1/wardrobe").json()

    assert body["count"] == 2
    assert [p["id"] for p in body["items"]] == [ids["heels"], ids["jeans"]]


def test_removing_takes_it_out_but_it_still_shapes_the_feed(api, ids):
    for name in ("dress", "heels", "belt"):
        _swipe(api, ids[name])

    response = api.client.delete(f"/v1/wardrobe/{ids['belt']}")

    assert response.status_code == 204
    assert ids["belt"] not in _wardrobe_ids(api)
    feed = api.client.get("/v1/feed").json()
    assert feed["personalised"] is True and feed["likes"] == 3  # still counts as a like
    row = api.interactions.rows[-1]
    assert row["type"] == "remove" and row["source"] == "wardrobe"


def test_a_removed_garment_returns_to_the_feed_after_the_cool_down(api, ids, monkeypatch):
    from ml import constants

    monkeypatch.setattr(constants, "REMOVE_COOLDOWN_SWIPES", 2)
    _swipe(api, ids["belt"])
    api.client.delete(f"/v1/wardrobe/{ids['belt']}")

    def shown():
        return {i["product"]["id"] for i in api.client.get("/v1/feed").json()["items"]}

    assert ids["belt"] not in shown()
    _swipe(api, ids["dress"], "dislike")
    assert ids["belt"] not in shown()
    _swipe(api, ids["heels"], "dislike")
    assert ids["belt"] in shown()


def test_removing_something_not_in_the_wardrobe_is_404(api, ids):
    _swipe(api, ids["jeans"], "dislike")

    assert api.client.delete(f"/v1/wardrobe/{ids['jeans']}").status_code == 404
    assert api.client.delete(f"/v1/wardrobe/{ids['dress']}").status_code == 404


def test_wardrobes_are_private(api, ids):
    _swipe(api, ids["jeans"])
    api.sign_in_as(USER_B)

    assert _wardrobe_ids(api) == []
    assert api.client.delete(f"/v1/wardrobe/{ids['jeans']}").status_code == 404
