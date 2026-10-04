"""Stage 4 CLI — load the selected articles into the products table.

    cd backend
    python -m scripts.load_catalog --subset ../data/subset.csv

Safe to re-run: rows are upserted on (source, source_id), so a second run
updates the same articles rather than duplicating them. Row-building logic
lives in ml/catalog.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.core.supabase_client import get_service_client
from ml.catalog import SOURCE, build_product_row

BATCH_SIZE = 500


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", required=True, type=Path)
    args = parser.parse_args()

    settings = get_settings()
    bucket = settings.PRODUCT_IMAGE_BUCKET
    if not bucket:
        raise SystemExit("Set PRODUCT_IMAGE_BUCKET in backend/.env first.")

    subset = pd.read_csv(args.subset, dtype={"article_id": str, "product_code": str})
    rows = [
        build_product_row(record, settings.SUPABASE_URL, bucket)
        for record in subset.to_dict("records")
    ]

    client = get_service_client()
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        client.table("products").upsert(batch, on_conflict="source,source_id").execute()
        print(f"upserted {start + len(batch)}/{len(rows)}")

    total = (
        client.table("products")
        .select("id", count="exact")
        .eq("source", SOURCE)
        .execute()
    )
    print(f"done: {total.count} products with source='{SOURCE}'")


if __name__ == "__main__":
    main()
