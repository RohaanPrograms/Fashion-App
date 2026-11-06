from conftest import USER_A, USER_B


def _create(api, ids, names, name="Friday"):
    return api.client.post("/v1/outfits", json={"name": name, "product_ids": [ids[n] for n in names]})


def test_creating_an_outfit_returns_it_with_slots_and_total_price(api, ids):
    response = _create(api, ids, ["jeans", "black_tee", "sneakers"])

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Friday"
    assert [(i["slot"], i["product"]["name"]) for i in body["items"]] == [
        ("top", "black_tee"), ("bottom", "jeans"), ("shoes", "sneakers"),
    ]
    assert body["total_price"] == 75.0 and body["currency"] == "GBP"


def test_any_garment_can_go_in_an_outfit_not_only_wardrobe_items(api, ids):
    """Decided 2026-10-19: no wardrobe check. Nothing here has been liked."""
    assert api.interactions.rows == []

    assert _create(api, ids, ["dress", "heels"]).status_code == 201


def test_too_few_or_too_many_items_is_422(api, ids):
    assert _create(api, ids, ["jeans"]).status_code == 422
    six = ["black_tee", "jeans", "dress", "heels", "belt", "striped_tee"]
    assert _create(api, ids, six).status_code == 422


def test_two_items_for_one_slot_is_422_with_a_plain_message(api, ids):
    response = _create(api, ids, ["black_tee", "striped_tee"])

    assert response.status_code == 422
    assert response.json()["detail"] == "Two items for the top slot: black_tee and striped_tee."


def test_a_dress_with_jeans_is_422_with_a_plain_message(api, ids):
    response = _create(api, ids, ["dress", "jeans"])

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "A full-body item can't be combined with a top or bottom: dress and jeans."
    )
    assert api.outfits.outfits == []


def test_an_unknown_garment_is_404(api, ids):
    response = api.client.post(
        "/v1/outfits",
        json={"name": "x", "product_ids": [ids["jeans"], "99999999-0000-4000-8000-000000000000"]},
    )

    assert response.status_code == 404


def test_a_blank_name_is_422(api, ids):
    assert _create(api, ids, ["jeans", "black_tee"], name="   ").status_code == 422


def test_listing_shows_only_my_outfits_newest_first(api, ids):
    _create(api, ids, ["jeans", "black_tee"], name="first")
    _create(api, ids, ["dress", "heels"], name="second")
    api.sign_in_as(USER_B)
    _create(api, ids, ["jeans", "sneakers"], name="not mine")
    api.sign_in_as(USER_A)

    names = [o["name"] for o in api.client.get("/v1/outfits").json()["outfits"]]

    assert names == ["second", "first"]


def test_the_total_is_computed_on_read_from_current_prices(api, ids, small_catalog):
    """No stored total: change a price and the listed total follows."""
    from dataclasses import replace

    from app.recs.catalog import Catalog, catalog_state

    _create(api, ids, ["jeans", "black_tee"])
    repriced = [replace(p, price=99.0) if p.name == "jeans" else p for p in small_catalog.products]
    catalog_state.set(Catalog(repriced, small_catalog.vectors, small_catalog.model_version))

    (outfit,) = api.client.get("/v1/outfits").json()["outfits"]

    assert outfit["total_price"] == 109.0


def test_deleting_my_outfit_is_204_and_someone_elses_is_404(api, ids):
    mine = _create(api, ids, ["jeans", "black_tee"]).json()["id"]
    api.sign_in_as(USER_B)
    theirs = _create(api, ids, ["dress", "heels"]).json()["id"]
    api.sign_in_as(USER_A)

    assert api.client.delete(f"/v1/outfits/{theirs}").status_code == 404
    assert api.client.delete(f"/v1/outfits/{mine}").status_code == 204
    assert api.client.get("/v1/outfits").json()["outfits"] == []
    assert len(api.outfits.outfits) == 1  # theirs survived
