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


@pytest.mark.parametrize("count", [0, 1, 6])
def test_an_outfit_needs_two_to_five_items(small_catalog, ids, count):
    names = ["black_tee", "jeans", "dress", "heels", "belt", "striped_tee"][:count]

    with pytest.raises(OutfitRuleError, match="2–5 items"):
        plan_outfit(small_catalog, [ids[n] for n in names])


def test_one_item_per_slot(small_catalog, ids):
    with pytest.raises(OutfitRuleError, match="top slot: black_tee and striped_tee"):
        plan_outfit(small_catalog, [ids["black_tee"], ids["striped_tee"], ids["jeans"]])


def test_a_full_body_item_cannot_be_worn_with_a_top(small_catalog, ids):
    with pytest.raises(OutfitRuleError, match="full-body item can't be combined.*: dress and black_tee"):
        plan_outfit(small_catalog, [ids["black_tee"], ids["dress"]])


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
