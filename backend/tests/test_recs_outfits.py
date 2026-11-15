import pytest

from app.recs.outfits import (
    OutfitRuleError,
    UnknownProductError,
    plan_outfit,
    slot_for,
    total_price,
)


def test_every_catalogue_category_has_a_slot(small_catalog, ids):
    slots = {name: slot_for(small_catalog.product(pid)) for name, pid in ids.items()}

    assert slots["black_tee"] == "top"
    assert slots["jeans"] == "bottom"
    assert slots["dress"] == "full_body"
    assert slots["heels"] == "shoes"
    assert slots["belt"] == "accessory"


@pytest.mark.parametrize("count", [0, 1, 21])
def test_an_outfit_needs_two_to_twenty_items(small_catalog, ids, count):
    """20 is a safety cap, not a design limit: jewellery has no limit of its own."""
    with pytest.raises(OutfitRuleError, match="2–20 items"):
        plan_outfit(small_catalog, [ids["belt"]] * count)


def test_one_item_per_slot(small_catalog, ids):
    with pytest.raises(OutfitRuleError, match="top slot: black_tee and striped_tee"):
        plan_outfit(small_catalog, [ids["black_tee"], ids["striped_tee"], ids["jeans"]])


def test_a_top_can_be_worn_under_a_full_body_item(small_catalog, ids):
    """Layering (2026-11-15): a tank or long-sleeve under a dress is fine."""
    planned = plan_outfit(small_catalog, [ids["black_tee"], ids["dress"]])

    assert [slot for _, slot in planned] == ["top", "full_body"]


def test_a_full_body_item_cannot_be_worn_with_a_bottom(small_catalog, ids):
    with pytest.raises(OutfitRuleError, match="full-body item can't be combined.*: dress and jeans"):
        plan_outfit(small_catalog, [ids["dress"], ids["jeans"], ids["heels"]])


def test_a_full_body_item_goes_with_shoes_and_an_accessory(small_catalog, ids):
    planned = plan_outfit(small_catalog, [ids["dress"], ids["heels"], ids["belt"]])

    assert [slot for _, slot in planned] == ["full_body", "shoes", "accessory"]


def test_the_same_garment_twice_is_refused(small_catalog, ids):
    with pytest.raises(OutfitRuleError, match="twice"):
        plan_outfit(small_catalog, [ids["jeans"], ids["jeans"]])


def test_an_unknown_garment_is_reported_by_id(small_catalog, ids):
    with pytest.raises(UnknownProductError) as caught:
        plan_outfit(small_catalog, [ids["jeans"], "missing-id"])

    assert caught.value.product_id == "missing-id"


def test_a_valid_outfit_lists_each_item_with_its_slot(small_catalog, ids):
    planned = plan_outfit(small_catalog, [ids["black_tee"], ids["jeans"], ids["sneakers"]])

    assert [(p.name, slot) for p, slot in planned] == [
        ("black_tee", "top"), ("jeans", "bottom"), ("sneakers", "shoes"),
    ]


def test_total_price_adds_up_and_ignores_unknown_prices(small_catalog, ids):
    tee, jeans = small_catalog.product(ids["black_tee"]), small_catalog.product(ids["jeans"])

    from dataclasses import replace

    unpriced = replace(jeans, price=None)

    assert total_price([tee, jeans]) == 40.0
    assert total_price([tee, unpriced]) == 10.0
    assert total_price([unpriced]) is None
    assert total_price([]) is None


# --- Layering ------------------------------------------------------------------
# A "layer" row for outer pieces. Jumpers and shirts can be worn either way;
# jackets, blazers, cardigans and hoodies only as a layer; everything else in
# Tops only as a top.

_LAYERED = {
    # name: (category, garment type)
    "tank": ("Garment Upper body", "Vest top"),
    "tee": ("Garment Upper body", "T-shirt"),
    "shirt": ("Garment Upper body", "Shirt"),
    "jumper": ("Garment Upper body", "Sweater"),
    "jacket": ("Garment Upper body", "Jacket"),
    "cardigan": ("Garment Upper body", "Cardigan"),
    "hoodie": ("Garment Upper body", "Hoodie"),
    "dress": ("Garment Full body", "Dress"),
    "jeans": ("Garment Lower body", "Trousers"),
    "boots": ("Shoes", "Boots"),
    "bag": ("Accessories", "Bag"),
    "purse": ("Accessories", "Bag"),
    "cap": ("Accessories", "Cap/peaked"),
    "beanie": ("Accessories", "Hat/beanie"),
    "necklace": ("Accessories", "Necklace"),
    "ring": ("Accessories", "Ring"),
    "earrings": ("Accessories", "Earring"),
    "bracelet": ("Accessories", "Bracelet"),
    "shades": ("Accessories", "Sunglasses"),
    "belt": ("Accessories", "Belt"),
    "clip": ("Accessories", "Hair clip"),
    "band": ("Accessories", "Hair/alice band"),
}


@pytest.fixture
def layered():
    from app.recs.catalog import build_catalog
    from conftest import product_row

    products, vectors, ids = [], [], {}
    for i, (name, (category, kind)) in enumerate(_LAYERED.items()):
        pid = f"00000000-0000-4000-a000-{i:012d}"
        ids[name] = pid
        row = product_row(pid, name, category, f"L{i}", 100 - i, 10.0)
        row["attributes"]["type"] = kind
        products.append(row)
        vectors.append({"product_id": pid, "vector": [1.0, float(i)], "model_version": "v"})
    return build_catalog(products, vectors), ids


def _plan(layered, *names, slots=None):
    catalog, ids = layered
    return [(p.name, slot) for p, slot in plan_outfit(catalog, [ids[n] for n in names], slots)]


def test_each_garment_type_has_its_rows(layered):
    from app.recs.outfits import allowed_slots

    catalog, ids = layered
    rows = {name: allowed_slots(catalog.product(pid)) for name, pid in ids.items()}
    assert rows["tank"] == ["top"] and rows["tee"] == ["top"]
    assert rows["jacket"] == ["layer"] and rows["cardigan"] == ["layer"] and rows["hoodie"] == ["layer"]
    assert set(rows["jumper"]) == {"top", "layer"} and set(rows["shirt"]) == {"top", "layer"}
    assert rows["dress"] == ["full_body"] and rows["jeans"] == ["bottom"]


def test_a_tee_under_a_jacket(layered):
    assert _plan(layered, "tee", "jacket", "jeans", "boots", "bag") == [
        ("tee", "top"), ("jacket", "layer"), ("jeans", "bottom"), ("boots", "shoes"), ("bag", "accessory"),
    ]


def test_a_tank_under_a_dress_with_a_cardigan_over_it(layered):
    assert _plan(layered, "tank", "dress", "cardigan", "boots", "bag") == [
        ("tank", "top"), ("dress", "full_body"), ("cardigan", "layer"), ("boots", "shoes"), ("bag", "accessory"),
    ]


def test_a_dress_still_cannot_go_with_a_bottom(layered):
    with pytest.raises(OutfitRuleError, match="full-body item can't be combined with a bottom"):
        _plan(layered, "dress", "jeans")


def test_two_layers_are_refused(layered):
    with pytest.raises(OutfitRuleError, match="layer slot: jacket and cardigan"):
        _plan(layered, "tee", "jacket", "cardigan")


def test_a_jumper_or_shirt_is_worn_the_way_you_choose(layered):
    assert _plan(layered, "jumper", "jeans", slots=["top", None]) == [("jumper", "top"), ("jeans", "bottom")]
    assert _plan(layered, "tee", "jumper", slots=[None, "layer"]) == [("tee", "top"), ("jumper", "layer")]
    # An open shirt over a tank: the case a single Top row couldn't do.
    assert _plan(layered, "tank", "shirt", slots=[None, "layer"]) == [("tank", "top"), ("shirt", "layer")]


def test_without_a_choice_a_jumper_is_a_layer_and_a_shirt_a_top(layered):
    assert _plan(layered, "tee", "jumper") == [("tee", "top"), ("jumper", "layer")]
    assert _plan(layered, "shirt", "jeans") == [("shirt", "top"), ("jeans", "bottom")]


def test_a_role_a_garment_cannot_play_is_refused(layered):
    with pytest.raises(OutfitRuleError, match="jacket can't be worn as a top"):
        _plan(layered, "jacket", "jeans", slots=["top", None])
    with pytest.raises(OutfitRuleError, match="tee can't be worn as a layer"):
        _plan(layered, "tee", "jeans", slots=["layer", None])



# --- Several accessories ------------------------------------------------------
# One bag, one hat, one pair of sunglasses, one belt, one scarf; as much
# jewellery and as many hair accessories as you like.

def test_as_much_jewellery_as_you_like(layered):
    planned = _plan(layered, "tee", "jeans", "necklace", "ring", "earrings", "bracelet", "bag", "shades")

    assert [slot for _, slot in planned].count("accessory") == 6


def test_several_hair_accessories_are_fine(layered):
    assert len(_plan(layered, "tee", "jeans", "clip", "band")) == 4


@pytest.mark.parametrize("first, second, what", [("bag", "purse", "bag"), ("cap", "beanie", "hat")])
def test_only_one_bag_or_hat(layered, first, second, what):
    with pytest.raises(OutfitRuleError, match=f"Only one {what} per set: {first} and {second}"):
        _plan(layered, "tee", first, second)


def test_a_bag_a_hat_and_jewellery_together(layered):
    planned = _plan(layered, "tee", "jeans", "bag", "cap", "necklace", "ring")
    assert [p for p, _ in planned] == ["tee", "jeans", "bag", "cap", "necklace", "ring"]
