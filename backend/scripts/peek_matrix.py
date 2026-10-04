"""Print a small, readable slice of the training matrix and its index mapping.

    cd backend
    python -m scripts.peek_matrix --customers 3
    python -m scripts.peek_matrix --customers 5 --seed 42   # random customers

Shows the first few entries of both mapping lists, then a handful of
customers' purchases twice: as the raw list from train.parquet, and as the
same numbers in the customer x article grid. Exploration only; nothing is
written anywhere.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ml.matrix import build_interaction_matrix


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("../data"))
    parser.add_argument("--customers", type=int, default=3)
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Pick random customers with this seed (default: first ones in the list).",
    )
    args = parser.parse_args()

    print("Building the matrix (takes a few seconds)...")
    transactions = pd.read_parquet(
        args.data_dir / "train.parquet", columns=["customer_id", "article_id"]
    )
    matrix, mapping = build_interaction_matrix(transactions)
    names = pd.read_csv(
        args.data_dir / "subset.csv", dtype={"article_id": str}
    ).set_index("article_id")["prod_name"]

    print(f"\n=== CUSTOMER LIST (first 5 of {len(mapping.customer_ids):,})")
    for i in range(5):
        print(f"  row {i:>6}  ->  {mapping.customer_ids[i][:16]}...")
    print(f"\n=== ARTICLE LIST (first 5 of {len(mapping.article_ids):,})")
    for i in range(5):
        article_id = mapping.article_at(i)
        print(f"  column {i:>4}  ->  {article_id}  {names[article_id]}")

    # Customers with 3-5 purchases: enough to see something, few enough to read.
    counts = transactions["customer_id"].value_counts()
    candidates = counts[(counts >= 3) & (counts <= 5)].index
    if args.seed is None:
        picked = sorted(candidates)[: args.customers]
    else:
        picked = sorted(pd.Series(candidates).sample(args.customers, random_state=args.seed))
    rows = [mapping.customer_position(c) for c in picked]
    cols = sorted({int(c) for r in rows for c in matrix[r].indices})

    print(f"\n=== RAW PURCHASE LIST for {len(picked)} customers")
    raw = transactions[transactions["customer_id"].isin(picked)].copy()
    raw["customer_id"] = raw["customer_id"].astype(str).str[:8] + "..."
    raw["name"] = raw["article_id"].map(names)
    print(raw.sort_values(["customer_id", "article_id"]).to_string(index=False))

    print("\n=== THE SAME PURCHASES AS A GRID (only the columns these customers bought)")
    grid = pd.DataFrame(
        matrix[rows][:, cols].toarray().astype(int),
        index=[f"row {r} ({c[:8]}...)" for r, c in zip(rows, picked)],
        columns=[f"col {c}" for c in cols],
    )
    print(grid.to_string())

    print("\nColumn key:")
    for c in cols:
        article_id = mapping.article_at(c)
        print(f"  col {c:>4} = {article_id}  {names[article_id]}")
    print(
        f"\nThe full grid has {matrix.shape[1]:,} columns; the other "
        f"{matrix.shape[1] - len(cols):,} are all 0 for these customers."
    )


if __name__ == "__main__":
    main()
