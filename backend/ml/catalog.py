"""Stage 4 — turn selected H&M articles into rows for the products table.

The H&M dataset has no prices. Rather than leave the field null — which would
make the set-builder's total price meaningless — a deterministic price is
derived from the article id, so the same garment always shows the same price.
Prices are synthetic and the README says so.
"""

from __future__ import annotations

import random

import pandas as pd

SOURCE = "hm"

# Rough price bands by category, in GBP. Synthetic — see module docstring.
PRICE_BANDS = {
    "Garment Upper body": (12, 45),
    "Garment Lower body": (18, 55),
    "Garment Full body": (25, 80),
    "Shoes": (30, 95),
    "Accessories": (5, 30),
}
DEFAULT_PRICE_BAND = (10, 50)


def price_for(article_id: str, category: str) -> float:
    low, high = PRICE_BANDS.get(category, DEFAULT_PRICE_BAND)
    # Seeded on the article id so the price is stable across re-runs.
    rng = random.Random(article_id)
    return round(rng.uniform(low, high), 2)


def image_url(base_url: str, bucket: str, article_id: str) -> str:
    return f"{base_url}/storage/v1/object/public/{bucket}/{article_id}.webp"


def _text(value) -> str | None:
    """pandas reads empty cells as NaN, which JSON cannot carry; send null instead."""
    return None if pd.isna(value) else str(value)


def build_product_row(record: dict, base_url: str, bucket: str) -> dict:
    """One row of data/subset.csv -> one row of public.products."""
    article_id = record["article_id"]
    category = record["product_group_name"]
    return {
        "source": SOURCE,
        "source_id": article_id,
        "name": _text(record.get("prod_name")) or f"Article {article_id}",
        "brand": "H&M",
        "url": f"https://www2.hm.com/en_gb/productpage.{article_id}.html",
        "price": price_for(article_id, category),
        "currency": "GBP",
        "image_url": image_url(base_url, bucket, article_id),
        "in_stock": True,
        "category": category,
        "product_code": _text(record.get("product_code")),
        "popularity": int(record["popularity"]),
        "attributes": {
            "colour": _text(record.get("colour_group_name")),
            "garment_group": _text(record.get("garment_group_name")),
            "department": _text(record.get("department_name")),
            "appearance": _text(record.get("graphical_appearance_name")),
        },
    }
