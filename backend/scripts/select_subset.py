"""Stage 1 CLI — write the chosen catalog articles to disk.

    cd backend
    python -m scripts.select_subset --data-dir ../data/hm --out ../data/subset.csv

Every later stage reads this file, so the whole pipeline operates on an
identical set of articles even if it is re-run days apart.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ml.constants import CATEGORY_QUOTAS, HOLDOUT_DAYS, TRAINING_WINDOW_MONTHS
from ml.selection import count_training_window_purchases, select_catalog_subset
from scripts.hm_data import article_ids_to_str, load_transactions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    articles = pd.read_csv(
        args.data_dir / "articles.csv", dtype={"article_id": str, "product_code": str}
    )
    transactions = load_transactions(args.data_dir / "transactions_train.csv")

    counts = count_training_window_purchases(
        transactions, months=TRAINING_WINDOW_MONTHS, holdout_days=HOLDOUT_DAYS
    )
    counts.index = article_ids_to_str(counts.index)

    subset = select_catalog_subset(articles, counts, CATEGORY_QUOTAS)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    subset.to_csv(args.out, index=False)

    print(f"Selected {len(subset)} articles -> {args.out}")
    print(subset["product_group_name"].value_counts().to_string())
    print(f"Fewest training-window purchases of any selected article: "
          f"{subset['popularity'].min()}")


if __name__ == "__main__":
    main()
