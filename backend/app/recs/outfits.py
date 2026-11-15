"""Outfit rules, pure: 2 to 20 garments; one per slot, except accessories.

SLOTS (rows in the app's builder), head to toe:
  top · full_body · layer · bottom · shoes · accessory

A garment's slot comes from its catalogue category and garment type, never
freely from the request, so the app cannot file a pair of shoes as a top.
Any catalogue garment may be used — not only wardrobe items (a deliberate
choice; tests pin it down).

LAYERING (added 2026-11-15, tester feedback)
--------------------------------------------
Outer pieces have their own "layer" slot, so a set can be a tee under a
jacket, or a tank under a dress with a cardigan over it. A few garment types
are worn both ways (a jumper on its own or over a shirt; a shirt on its own
or open over a tank): for those the request may say which role it plays, and
without one the first allowed slot is used. A full-body garment (a dress, a
jumpsuit) covers the legs, so it can't be combined with a bottom; it can now
go with a top under it and a layer over it.

SEVERAL ACCESSORIES (added 2026-11-15, user's rule)
---------------------------------------------------
The accessory slot holds several items, by kind: one bag, one hat, one pair
of sunglasses, one belt, one scarf; as much jewellery and as many hair
accessories as you like. 20 items is a safety cap on the request, not a
design limit.
"""

from __future__ import annotations

from app.recs.catalog import Catalog, Product

SLOT_BY_CATEGORY = {
    "Garment Upper body": "top",
    "Garment Lower body": "bottom",
    "Garment Full body": "full_body",
    "Shoes": "shoes",
    "Accessories": "accessory",
}
# Upper-body garment types (H&M product_type_name) that aren't plain tops.
# The first slot listed is the default when the request doesn't choose.
UPPER_BODY_SLOTS_BY_TYPE = {
    "Jacket": ["layer"],
    "Blazer": ["layer"],
    "Cardigan": ["layer"],
    "Hoodie": ["layer"],
    "Sweater": ["layer", "top"],  # a jumper: usually over something
    "Shirt": ["top", "layer"],  # usually on its own; open over a tank
}
# Accessory kinds (H&M product_type_name -> kind) and how many of each a set
# may hold; None = no limit. A type not listed counts as "other": one.
ACCESSORY_KIND_BY_TYPE = {
    "Bag": "bag",
    **{t: "hat" for t in ("Hat/brim", "Hat/beanie", "Bucket hat", "Straw hat", "Felt hat", "Cap/peaked", "Cap")},
    **{t: "jewellery" for t in ("Earring", "Earrings", "Necklace", "Ring", "Bracelet")},
    "Sunglasses": "sunglasses",
    "Belt": "belt",
    "Braces": "belt",
    "Scarf": "scarf",
    "Other accessories": "scarf",
    **{t: "hair" for t in ("Hair/alice band", "Hair string", "Hair ties", "Hair clip", "Hairband")},
}
ACCESSORY_LIMITS = {"bag": 1, "hat": 1, "sunglasses": 1, "belt": 1, "scarf": 1, "other": 1,
                    "jewellery": None, "hair": None}
ACCESSORY_NAMES = {"bag": "bag", "hat": "hat", "sunglasses": "pair of sunglasses", "belt": "belt",
                   "scarf": "scarf", "other": "accessory of this kind"}
ACCESSORY = "accessory"

# Head to toe, for showing an outfit's items in a sensible order: what's
# under, the dress, what's over it, then the legs, feet, extras.
SLOT_ORDER = ["top", "full_body", "layer", "bottom", "shoes", "accessory"]
MIN_ITEMS, MAX_ITEMS = 2, 20
FULL_BODY = "full_body"
COVERED_BY_FULL_BODY = ("bottom",)


class OutfitRuleError(ValueError):
    """The outfit breaks a rule; the message says which, in plain words."""


class UnknownProductError(KeyError):
    def __init__(self, product_id: str):
        super().__init__(product_id)
        self.product_id = product_id


def allowed_slots(product: Product) -> list[str]:
    """Every slot this garment can go in, the default first."""
    slot = SLOT_BY_CATEGORY.get(product.category or "")
    if slot is None:
        raise OutfitRuleError(f"{product.name} cannot go in an outfit (category {product.category!r}).")
    if slot == "top":
        return list(UPPER_BODY_SLOTS_BY_TYPE.get(product.product_type or "", ["top"]))
    return [slot]


def accessory_kind(product: Product) -> str:
    return ACCESSORY_KIND_BY_TYPE.get(product.product_type or "", "other")


def slot_for(product: Product) -> str:
    """The slot a garment goes in when the request doesn't choose."""
    return allowed_slots(product)[0]


def plan_outfit(
    catalog: Catalog, product_ids: list[str], slots: list[str | None] | None = None
) -> list[tuple[Product, str]]:
    """Check the rules and return each garment with its slot, in request order.

    `slots`, if given, is one entry per garment: the role it plays ("top" or
    "layer" for a jumper, say), or None for its default.
    """
    if not MIN_ITEMS <= len(product_ids) <= MAX_ITEMS:
        raise OutfitRuleError(
            f"An outfit needs {MIN_ITEMS}–{MAX_ITEMS} items, got {len(product_ids)}."
        )
    if len(set(product_ids)) != len(product_ids):
        raise OutfitRuleError("The same garment appears twice.")
    if slots is not None and len(slots) != len(product_ids):
        raise OutfitRuleError("Give one role per garment, or none at all.")

    taken: dict[str, Product] = {}  # one-per-slot rows
    worn: dict[str, Product] = {}  # accessory kind -> the first of that kind
    planned: list[tuple[Product, str]] = []
    for i, product_id in enumerate(product_ids):
        product = catalog.product(product_id)
        if product is None:
            raise UnknownProductError(product_id)
        options = allowed_slots(product)
        chosen = slots[i] if slots is not None else None
        if chosen is not None and chosen not in options:
            raise OutfitRuleError(
                f"{product.name} can't be worn as a {chosen.replace('_', ' ')}."
            )
        slot = chosen or options[0]
        if slot == ACCESSORY:
            kind = accessory_kind(product)
            if ACCESSORY_LIMITS.get(kind, 1) is not None and kind in worn:
                raise OutfitRuleError(
                    f"Only one {ACCESSORY_NAMES.get(kind, 'accessory of this kind')} per set: "
                    f"{worn[kind].name} and {product.name}."
                )
            worn.setdefault(kind, product)
            planned.append((product, slot))
            continue
        if slot in taken:
            raise OutfitRuleError(
                f"Two items for the {slot.replace('_', ' ')} slot: "
                f"{taken[slot].name} and {product.name}."
            )
        taken[slot] = product
        planned.append((product, slot))

    full_body = taken.get(FULL_BODY)
    clash = next((taken[s] for s in COVERED_BY_FULL_BODY if s in taken), None)
    if full_body is not None and clash is not None:
        raise OutfitRuleError(
            "A full-body item can't be combined with a bottom: "
            f"{full_body.name} and {clash.name}."
        )
    return planned


def total_price(products: list[Product]) -> float | None:
    """Computed on every read, never stored: a stored total goes stale."""
    prices = [p.price for p in products if p.price is not None]
    return round(sum(prices), 2) if prices else None
