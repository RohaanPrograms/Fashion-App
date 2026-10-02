"""Fill the products table with placeholder catalogue data for development.

WHY THIS EXISTS
---------------
The real catalogue comes from an affiliate feed (ASOS via AWIN etc.), and
getting approved for those can take weeks. But none of the Phase 1 work — the
swipe feed, interaction logging, dwell tracking — actually needs *real*
products; it needs *rows in the products table*. This script generates a few
hundred believable ones so you can build the whole app now and swap in the real
feed later without changing a line of downstream code.

Everything it inserts is tagged  source = 'seed'. That keeps it completely
separate from real data (which arrives as source = 'asos', 'farfetch', ...) and
makes it a one-liner to remove later:

    delete from public.products where source = 'seed';

HOW TO RUN
----------
    cd backend
    python -m scripts.seed_products            # inserts the default 120 items
    python -m scripts.seed_products --count 300
    python -m scripts.seed_products --clear    # remove all seed rows, then stop

It is safe to run repeatedly: rows are upserted on (source, source_id), so a
second run updates the same 120 items instead of creating duplicates.

Uses the SERVICE ROLE key (from backend/.env), which is allowed to write to
products. The mobile app can only read them — see the RLS policies in
supabase/schema.sql.
"""

from __future__ import annotations

import argparse
import random

from app.core.supabase_client import get_service_client

# A fixed seed means "item 0007" is the same navy hoodie on every run, so
# re-running updates rows in place rather than churning the catalogue.
RNG = random.Random(1234)

# Invented brand names. Deliberately not real brands: attaching made-up prices
# to a real label would be misleading if these rows ever leaked into a screenshot.
BRANDS = [
    "Atlas & Oak", "Maison Reeve", "Northlane", "Verde Studio", "Halcyon",
    "Kestrel", "Bower & Co", "Fernwood", "Otta", "Lumen", "Saga", "Wren",
    "Mode Ora", "Kin", "Petra", "Isla", "Aubin", "Rowan",
]

COLOURS = [
    "Black", "White", "Navy", "Beige", "Grey", "Olive", "Burgundy", "Cream",
    "Brown", "Sage", "Charcoal", "Tan", "Blush", "Rust", "Ecru",
]

MATERIALS = ["Cotton", "Linen", "Wool", "Denim", "Leather", "Cashmere", "Silk", "Corduroy"]
FITS = ["Slim", "Regular", "Oversized", "Relaxed", "Tailored", "Cropped"]
OCCASIONS = ["Casual", "Work", "Evening", "Weekend", "Formal", "Sport"]

# Each garment type carries a rough gender lean and a typical price band, so the
# generated catalogue is varied enough to test budget/gender filters later.
# Price band is (low, high) in GBP, matching the onboarding budget buckets.
CATEGORIES = [
    # (name, category, gender, price_low, price_high)
    ("T-Shirt",       "tops",      "both",   12,  35),
    ("Shirt",         "tops",      "both",   25,  70),
    ("Blouse",        "tops",      "womens", 25,  80),
    ("Hoodie",        "tops",      "both",   30,  90),
    ("Sweater",       "knitwear",  "both",   35, 120),
    ("Polo Shirt",    "tops",      "mens",   20,  60),
    ("Jeans",         "bottoms",   "both",   30, 110),
    ("Trousers",      "bottoms",   "both",   35, 130),
    ("Chinos",        "bottoms",   "mens",   30,  85),
    ("Shorts",        "bottoms",   "both",   18,  55),
    ("Skirt",         "bottoms",   "womens", 22,  90),
    ("Leggings",      "activewear","womens", 20,  60),
    ("Jacket",        "outerwear", "both",   50, 220),
    ("Coat",          "outerwear", "both",   70, 300),
    ("Blazer",        "outerwear", "both",   55, 200),
    ("Bomber Jacket", "outerwear", "both",   45, 160),
    ("Midi Dress",    "dresses",   "womens", 35, 140),
    ("Maxi Dress",    "dresses",   "womens", 40, 180),
    ("Mini Dress",    "dresses",   "womens", 30, 120),
    ("Sneakers",      "footwear",  "both",   40, 160),
    ("Boots",         "footwear",  "both",   55, 220),
    ("Loafers",       "footwear",  "both",   45, 170),
]

# The nine onboarding aesthetics (schema: users.style_clusters holds 'A'..'I').
# Tagging each product with one lets us test cluster-seeded feeds in Phase 1.
STYLE_CLUSTERS = [
    ("A", "Minimalist"), ("B", "Streetwear"), ("C", "Smart"),
    ("D", "Athleisure"), ("E", "Boho"), ("F", "Vintage"),
    ("G", "Quiet Luxury"), ("H", "Y2K"), ("I", "Everyday"),
]


def build_product(i: int) -> dict:
    """Assemble one believable product row."""
    name_part, category, gender, lo, hi = RNG.choice(CATEGORIES)
    brand = RNG.choice(BRANDS)
    colour = RNG.choice(COLOURS)
    fit = RNG.choice(FITS)
    cluster_id, cluster_name = RNG.choice(STYLE_CLUSTERS)

    source_id = f"seed-{i:04d}"
    # Price to a realistic .99/.00 ending within the garment's band.
    price = round(RNG.uniform(lo, hi)) - 0.01

    return {
        "source": "seed",
        "source_id": source_id,
        "name": f"{brand} {colour} {fit} {name_part}",
        "brand": brand,
        # Placeholder link — replaced by a real affiliate deep link once a
        # network is approved. example.com is reserved for exactly this use.
        "url": f"https://example.com/seed/{source_id}",
        "price": price,
        "currency": "GBP",
        # Lorem Picsum returns a stable image for a given seed. Not fashion
        # photography — good enough to build and test the feed layout against.
        "image_url": f"https://picsum.photos/seed/{source_id}/600/800",
        "in_stock": RNG.random() > 0.08,   # ~8% out of stock, to exercise that path
        "category": category,
        "attributes": {
            "colour": colour.lower(),
            "fit": fit.lower(),
            "material": RNG.choice(MATERIALS).lower(),
            "occasion": RNG.choice(OCCASIONS).lower(),
            "gender": gender,
            "style_cluster": cluster_id,
            "style_name": cluster_name,
        },
        "embedding_model_version": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed placeholder products for development.")
    parser.add_argument("--count", type=int, default=120, help="How many products to create.")
    parser.add_argument("--clear", action="store_true",
                        help="Delete all seed rows and exit (no new rows inserted).")
    args = parser.parse_args()

    client = get_service_client()

    if args.clear:
        client.table("products").delete().eq("source", "seed").execute()
        print("Removed all rows where source = 'seed'.")
        return

    rows = [build_product(i) for i in range(args.count)]

    # Upsert in batches on the (source, source_id) unique key. merge-duplicates
    # means a re-run overwrites the matching rows instead of erroring.
    BATCH = 100
    for start in range(0, len(rows), BATCH):
        chunk = rows[start:start + BATCH]
        client.table("products").upsert(chunk, on_conflict="source,source_id").execute()
        print(f"  upserted {start + len(chunk)}/{len(rows)}")

    total = (
        client.table("products")
        .select("id", count="exact")
        .eq("source", "seed")
        .execute()
    )
    print(f"Done. products table now holds {total.count} seed rows.")


if __name__ == "__main__":
    main()
