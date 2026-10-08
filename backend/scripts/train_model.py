"""Train ALS and write the item vectors into product_vectors.

    cd backend
    python -m scripts.train_model --train ../data/train.parquet --factors 64 [--scaling log]

Safe to re-run. product_id is the table's primary key, so each garment holds
exactly one vector: new vectors are upserted over the old ones first, and only
then are rows from any other model_version deleted. A run that fails midway
leaves the previous vectors in place rather than a half-empty table.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from app.core.supabase_client import get_service_client
from ml.catalog import SOURCE
from ml.matrix import build_interaction_matrix
from ml.train import (
    COUNT_SCALINGS,
    build_vector_rows,
    fetch_all_pages,
    model_version,
    train_als,
)

BATCH_SIZE = 500


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--factors", type=int, default=64)
    parser.add_argument("--scaling", choices=COUNT_SCALINGS, default="raw")
    args = parser.parse_args()

    transactions = pd.read_parquet(args.train)
    matrix, mapping = build_interaction_matrix(transactions)
    print(f"matrix: {matrix.shape[0]:,} customers x {matrix.shape[1]:,} articles")

    started = time.perf_counter()
    vectors = train_als(matrix, factors=args.factors, scaling=args.scaling)
    version = model_version(args.factors, args.scaling)
    print(f"trained {vectors.shape} as {version} in {time.perf_counter() - started:.1f}s")

    client = get_service_client()

    # Map article_id -> our products.id. Without this the vectors would attach
    # to the wrong rows, which is the failure mode ml/matrix.py warns about.
    # Ordered by id so the pages don't shift between requests.
    products = fetch_all_pages(
        lambda start, end: client.table("products")
        .select("id, source_id")
        .eq("source", SOURCE)
        .order("id")
        .range(start, end)
        .execute()
        .data
    )
    product_id_by_article = {row["source_id"]: row["id"] for row in products}

    rows, skipped = build_vector_rows(
        vectors, mapping.article_ids, product_id_by_article, version
    )

    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        client.table("product_vectors").upsert(batch).execute()
        print(f"stored {start + len(batch)}/{len(rows)}")

    client.table("product_vectors").delete().neq("model_version", version).execute()

    stored = (
        client.table("product_vectors")
        .select("product_id", count="exact")
        .eq("model_version", version)
        .execute()
    )
    print(
        f"done: {stored.count} vectors as {version} in the database; "
        f"{skipped} articles had no product row"
    )


if __name__ == "__main__":
    main()
