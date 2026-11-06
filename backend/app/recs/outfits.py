"""Outfit rules, pure: 2 to 5 garments, at most one per slot.

A garment's slot comes from its catalogue category, never from the request,
so the app cannot file a pair of shoes as a top. Any catalogue garment may be
used — not only wardrobe items (a deliberate choice; tests pin it down).

A full-body garment (a dress, a jumpsuit) already covers the top and bottom,
so it cannot be combined with either.
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
# Head to toe, for showing an outfit's items in a sensible order.
SLOT_ORDER = ["top", "full_body", "bottom", "shoes", "accessory"]
MIN_ITEMS, MAX_ITEMS = 2, 5
FULL_BODY = "full_body"
COVERED_BY_FULL_BODY = ("top", "bottom")


class OutfitRuleError(ValueError):
    """The outfit breaks a rule; the message says which, in plain words."""


class UnknownProductError(KeyError):
    def __init__(self, product_id: str):
        super().__init__(product_id)
        self.product_id = product_id


def slot_for(product: Product) -> str:
    slot = SLOT_BY_CATEGORY.get(product.category or "")
    if slot is None:
        raise OutfitRuleError(f"{product.name} cannot go in an outfit (category {product.category!r}).")
    return slot


def plan_outfit(catalog: Catalog, product_ids: list[str]) -> list[tuple[Product, str]]:
    """Check the rules and return each garment with its slot, in request order."""
    if not MIN_ITEMS <= len(product_ids) <= MAX_ITEMS:
        raise OutfitRuleError(
            f"An outfit needs {MIN_ITEMS}–{MAX_ITEMS} items, got {len(product_ids)}."
        )
    if len(set(product_ids)) != len(product_ids):
        raise OutfitRuleError("The same garment appears twice.")

    taken: dict[str, Product] = {}
    planned: list[tuple[Product, str]] = []
    for product_id in product_ids:
        product = catalog.product(product_id)
        if product is None:
            raise UnknownProductError(product_id)
        slot = slot_for(product)
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
            "A full-body item can't be combined with a top or bottom: "
            f"{full_body.name} and {clash.name}."
        )
    return planned


def total_price(products: list[Product]) -> float | None:
    """Computed on every read, never stored: a stored total goes stale."""
    prices = [p.price for p in products if p.price is not None]
    return round(sum(prices), 2) if prices else None
