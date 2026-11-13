"""The feed's filter list: well-formed, unambiguous, and strict about input."""

from pathlib import Path

import pandas as pd
import pytest

from app.recs.filters import FILTERS, UnknownFilter, parse_pick, select
from ml.constants import CATEGORY_QUOTAS


def test_categories_are_exactly_the_catalogue_groups():
    """A typo in product_group would silently make a category empty."""
    assert sorted(c.product_group for c in FILTERS) == sorted(CATEGORY_QUOTAS)


def test_keys_are_unique():
    assert len({c.key for c in FILTERS}) == len(FILTERS)
    for category in FILTERS:
        assert len({t.key for t in category.types}) == len(category.types)


def test_a_garment_type_belongs_to_one_button_only():
    seen: dict[str, str] = {}
    for category in FILTERS:
        for group in category.types:
            for name in group.types:
                assert name not in seen, f"{name} is in both {seen[name]} and {group.key}"
                seen[name] = group.key


def test_no_picks_means_no_filter():
    assert select([]) == []


def test_a_category_pick_keeps_every_type_in_it():
    selection = parse_pick("shoes")
    assert selection.product_group == "Shoes" and selection.types is None


def test_a_type_pick_narrows_its_category():
    selection = parse_pick("accessories:hats")
    assert selection.product_group == "Accessories"
    assert {"Hat/brim", "Cap", "Bucket hat"} <= selection.types


def test_picks_keep_their_order_without_repeats():
    picks = select(["tops:t-shirts", "accessories:sunglasses", "tops:t-shirts"])
    assert [p.types for p in picks] == [frozenset({"T-shirt"}), frozenset({"Sunglasses"})]


@pytest.mark.parametrize("pick", ["nope", "tops:sneakers", "tops:nope", ":t-shirts"])
def test_unknown_or_mismatched_picks_are_refused(pick):
    with pytest.raises(UnknownFilter):
        select([pick])


SUBSET = Path(__file__).resolve().parents[2] / "data" / "subset.csv"


@pytest.mark.skipif(not SUBSET.exists(), reason="needs the local data/subset.csv (not in the repo)")
def test_every_type_in_the_real_catalogue_has_a_button():
    """Runs on a machine with the data. A type with no button is still in its
    category's "All", but it should be a choice, not an accident."""
    subset = pd.read_csv(SUBSET, usecols=["product_type_name", "product_group_name"])
    grouped = {
        (c.product_group, name) for c in FILTERS for g in c.types for name in g.types
    }
    present = set(subset.itertuples(index=False, name=None))
    missing = {(group, t) for t, group in present} - grouped
    assert not missing
