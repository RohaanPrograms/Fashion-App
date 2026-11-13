"""The feed's filters: five categories, each with a handful of garment types.

PICKS
-----
The feed is filtered by one or more "picks", each a whole category ("tops")
or one type group in it ("tops:t-shirts"). With several picks the feed takes
turns between them (see app/recs/feed.py), so T-shirts + Sunglasses shows
some of each rather than whichever your taste leans towards.

THE ONE LIST
------------
The app does not keep its own copy: it asks GET /v1/feed/filters for this
list, so the buttons it shows and the filters the server accepts can never
disagree.

WHY TYPES ARE GROUPED
---------------------
H&M has ~60 garment types, some with only one or two items in the 5,000-item
catalogue ("Straw hat": 1). A button for each would run dry after a swipe or
two, so small types are merged into groups a shopper would recognise: every
hat is "Hats & caps", every earring, necklace and ring is "Jewellery".

A type missing from every group is still shown under its category's "All";
it just has no button of its own. Pure: no database, no network.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypeGroup:
    key: str  # in the URL: ?type=t-shirts
    label: str  # on the button
    types: frozenset[str]  # H&M product_type_name values


@dataclass(frozen=True)
class CategoryFilter:
    key: str  # in the URL: ?category=tops
    label: str
    product_group: str  # the `category` column: H&M product_group_name
    types: tuple[TypeGroup, ...]


def _group(key: str, label: str, *types: str) -> TypeGroup:
    return TypeGroup(key=key, label=label, types=frozenset(types))


FILTERS: tuple[CategoryFilter, ...] = (
    CategoryFilter("tops", "Tops", "Garment Upper body", (
        _group("t-shirts", "T-shirts", "T-shirt"),
        _group("vest-tops", "Vest tops", "Vest top"),
        _group("tops", "Tops", "Top", "Bodysuit"),
        _group("blouses", "Blouses", "Blouse"),
        _group("shirts", "Shirts & polos", "Shirt", "Polo shirt"),
        _group("knitwear", "Jumpers & cardigans", "Sweater", "Cardigan"),
        _group("hoodies", "Hoodies", "Hoodie"),
        _group("jackets", "Jackets & blazers", "Jacket", "Blazer"),
    )),
    CategoryFilter("bottoms", "Bottoms", "Garment Lower body", (
        # H&M files jeans, chinos and slacks all under "Trousers".
        _group("trousers", "Trousers & jeans", "Trousers"),
        _group("shorts", "Shorts", "Shorts"),
        _group("skirts", "Skirts", "Skirt"),
        _group("leggings", "Leggings & tights", "Leggings/Tights"),
    )),
    CategoryFilter("dresses", "Dresses", "Garment Full body", (
        _group("dresses", "Dresses", "Dress"),
        _group("jumpsuits", "Jumpsuits & more", "Jumpsuit/Playsuit", "Dungarees", "Costumes"),
    )),
    CategoryFilter("shoes", "Shoes", "Shoes", (
        _group("sneakers", "Sneakers", "Sneakers"),
        _group("sandals", "Sandals", "Sandals", "Flip flop"),
        _group("boots", "Boots", "Boots"),
        _group("heels", "Heels", "Heeled sandals", "Heels", "Pumps", "Wedge"),
        _group("flats", "Flats", "Ballerinas", "Flat shoe", "Flat shoes", "Slippers", "Other shoe"),
    )),
    CategoryFilter("accessories", "Accessories", "Accessories", (
        _group("bags", "Bags", "Bag"),
        _group("jewellery", "Jewellery", "Earring", "Earrings", "Necklace", "Ring", "Bracelet"),
        _group("belts", "Belts", "Belt", "Braces"),
        _group("sunglasses", "Sunglasses", "Sunglasses"),
        _group("hats", "Hats & caps", "Hat/brim", "Hat/beanie", "Bucket hat", "Straw hat",
               "Felt hat", "Cap/peaked", "Cap"),
        _group("hair", "Hair accessories", "Hair/alice band", "Hair string", "Hair ties",
               "Hair clip", "Hairband"),
        _group("scarves", "Scarves & more", "Scarf", "Other accessories"),
    )),
)


class UnknownFilter(ValueError):
    """The category or type isn't in FILTERS."""


@dataclass(frozen=True)
class Selection:
    """What one pick keeps: a product group, and optionally some garment types."""

    product_group: str
    types: frozenset[str] | None  # None: every type in the category


def parse_pick(pick: str) -> Selection:
    """One ?pick= value: "tops" (the whole category) or "tops:t-shirts"."""
    category_key, _, type_key = pick.partition(":")
    found = next((c for c in FILTERS if c.key == category_key), None)
    if found is None:
        raise UnknownFilter(f"No category '{category_key}'")
    if not type_key:
        return Selection(product_group=found.product_group, types=None)
    group = next((t for t in found.types if t.key == type_key), None)
    if group is None:
        raise UnknownFilter(f"No type '{type_key}' in '{category_key}'")
    return Selection(product_group=found.product_group, types=group.types)


def select(picks: list[str]) -> list[Selection]:
    """Every ?pick=, in the order given, without repeats. [] means no filter."""
    return [parse_pick(p) for p in dict.fromkeys(picks)]
