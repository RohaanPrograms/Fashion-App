import httpx

from app.db.interactions import get_interaction_store
from app.main import app
from conftest import USER_B


def _like(api, product_id):
    assert api.client.post("/v1/interactions", json={"product_id": product_id, "type": "like"}).status_code == 201


def _dislike(api, product_id):
    assert api.client.post("/v1/interactions", json={"product_id": product_id, "type": "dislike"}).status_code == 201


def test_a_new_user_gets_best_sellers(api, ids):
    body = api.client.get("/v1/feed", params={"limit": 2}).json()

    assert body["personalised"] is False
    assert body["likes"] == 0 and body["likes_needed"] == 3
    assert [i["product"]["id"] for i in body["items"]] == [ids["black_tee"], ids["jeans"]]
    first = body["items"][0]
    assert first["reason"] == {"kind": "popular", "similarity": None, "because_of": None}
    assert first["product"]["price"] == 10.0 and first["product"]["image_url"]


def test_three_likes_personalise_the_feed_and_explain_it(api, ids):
    for name in ("dress", "heels", "belt"):
        _like(api, ids[name])

    body = api.client.get("/v1/feed", params={"limit": 2}).json()

    assert body["personalised"] is True and body["likes"] == 3
    assert [i["product"]["id"] for i in body["items"]] == [ids["jeans"], ids["striped_tee"]]
    reason = body["items"][0]["reason"]
    assert reason["kind"] == "similar"
    assert reason["because_of"] == {"id": ids["belt"], "name": "belt"}


def test_swiped_garments_never_come_back(api, ids):
    swiped = [ids["black_tee"], ids["jeans"], ids["dress"]]
    _like(api, swiped[0])
    _dislike(api, swiped[1])
    _like(api, swiped[2])

    body = api.client.get("/v1/feed", params={"limit": 10}).json()

    shown = {i["product"]["id"] for i in body["items"]}
    assert not shown & set(swiped)


def test_cards_the_app_already_holds_are_not_sent_again(api, ids):
    """The app asks for the next batch before the last few cards are swiped.
    Without `exclude`, a new user's best-sellers would repeat those cards."""
    held = [ids["black_tee"], ids["jeans"]]

    body = api.client.get("/v1/feed", params={"limit": 2, "exclude": held}).json()

    # black_tee excluded, and white_tee with it (same design, other colour)
    assert [i["product"]["id"] for i in body["items"]] == [ids["dress"], ids["heels"]]
    assert api.interactions.rows == []  # excluding is not a vote


def test_exclude_is_capped(api, ids):
    assert api.client.get("/v1/feed", params={"exclude": [ids["jeans"]] * 50}).status_code == 200
    assert api.client.get("/v1/feed", params={"exclude": [ids["jeans"]] * 51}).status_code == 422


def test_each_user_gets_their_own_feed(api, ids):
    for name in ("dress", "heels", "belt"):
        _like(api, ids[name])
    api.sign_in_as(USER_B)

    body = api.client.get("/v1/feed").json()

    assert body["personalised"] is False and body["likes"] == 0


def test_the_batch_size_is_limited(api):
    assert api.client.get("/v1/feed", params={"limit": 0}).status_code == 422
    assert api.client.get("/v1/feed", params={"limit": 51}).status_code == 422
    assert len(api.client.get("/v1/feed").json()["items"]) == 7  # small catalogue: 7 designs


def test_the_feed_is_503_while_the_catalogue_is_missing(api):
    from app.recs.catalog import catalog_state

    catalog_state.set(None)

    assert api.client.get("/v1/feed").status_code == 503


def test_the_feed_is_503_during_a_supabase_outage(api):
    class DownStore:
        def history_rows(self, user_id):
            raise httpx.ReadTimeout("timed out")

    app.dependency_overrides[get_interaction_store] = lambda: DownStore()

    assert api.client.get("/v1/feed").status_code == 503


def test_a_product_can_be_fetched_by_id(api, ids):
    response = api.client.get(f"/v1/products/{ids['jeans']}")

    assert response.status_code == 200
    assert response.json()["name"] == "jeans"
    assert response.json()["category"] == "Garment Lower body"


def test_an_unknown_or_malformed_product_id(api):
    assert api.client.get("/v1/products/99999999-0000-4000-8000-000000000000").status_code == 404
    assert api.client.get("/v1/products/not-a-uuid").status_code == 422


def test_the_feed_can_be_filtered_by_category_or_type(api, ids):
    shoes = api.client.get("/v1/feed", params={"pick": "shoes"}).json()
    tees = api.client.get("/v1/feed", params={"pick": "tops:t-shirts"}).json()

    assert [i["product"]["id"] for i in shoes["items"]] == [ids["heels"], ids["sneakers"]]
    # one colour of design T1, then the striped tee
    assert [i["product"]["id"] for i in tees["items"]] == [ids["black_tee"], ids["striped_tee"]]


def test_likes_made_under_a_filter_count_toward_overall_taste(api, ids):
    for name in ("dress", "heels", "belt"):
        _like(api, ids[name])

    body = api.client.get("/v1/feed", params={"pick": "tops", "limit": 2}).json()

    assert body["personalised"] is True and body["likes"] == 3
    assert [i["product"]["id"] for i in body["items"]] == [ids["striped_tee"], ids["white_tee"]]


def test_unknown_filters_are_refused_with_a_reason(api):
    for params in ({"pick": "nope"}, {"pick": "tops:sneakers"}, {"pick": ["shoes", "tops:nope"]}):
        response = api.client.get("/v1/feed", params=params)
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], str)


def test_the_filter_list_is_public_and_complete(client):
    body = client.get("/v1/feed/filters").json()

    assert [c["key"] for c in body] == ["tops", "bottoms", "dresses", "shoes", "accessories"]
    tops = body[0]
    assert tops["label"] == "Tops"
    assert {"key": "t-shirts", "label": "T-shirts"} in tops["types"]


def test_several_picks_take_turns_over_http(api, ids):
    body = api.client.get("/v1/feed", params={"pick": ["tops:t-shirts", "shoes"], "limit": 4}).json()

    names = [i["product"]["id"] for i in body["items"]]
    assert names == [ids["black_tee"], ids["heels"], ids["striped_tee"], ids["sneakers"]]


def test_picks_are_capped(api):
    assert api.client.get("/v1/feed", params={"pick": ["shoes"] * 20}).status_code == 200
    assert api.client.get("/v1/feed", params={"pick": ["shoes"] * 21}).status_code == 422


def test_each_card_says_what_the_garment_is(api, ids):
    """The card's "About this piece" panel: type, pattern, description."""
    body = api.client.get("/v1/feed", params={"limit": 1}).json()

    product = body["items"][0]["product"]
    assert product["id"] == ids["black_tee"]
    assert product["type"] == "T-shirt"
    assert product["pattern"] == "Solid"
    assert product["colour"] == "Black"
    assert product["description"] == "A black tee."
