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

# article_id is 10 digits with a leading zero ("0108775015").
ARTICLE_ID_WIDTH = 10


def load_transactions(path: Path) -> pd.DataFrame:
    """Read only the two columns needed from the 31M-row file, compactly.

    Read as text, 31M article IDs take several GB of RAM. As integers they take
    ~250 MB, and ~730 distinct dates fit in a categorical (stored once each).
    """
    transactions = pd.read_csv(
        path,
        usecols=["t_dat", "article_id"],
        dtype={"t_dat": "category", "article_id": "int64"},
    )
    dates = transactions["t_dat"]
    transactions["t_dat"] = pd.to_datetime(dates.cat.categories)[dates.cat.codes]
    return transactions


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
    # Restore the leading zero lost by reading IDs as integers, to match articles.csv.
    counts.index = counts.index.astype(str).str.zfill(ARTICLE_ID_WIDTH)

    subset = select_catalog_subset(articles, counts, CATEGORY_QUOTAS)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    subset.to_csv(args.out, index=False)

    print(f"Selected {len(subset)} articles -> {args.out}")
    print(subset["product_group_name"].value_counts().to_string())
    print(f"Fewest training-window purchases of any selected article: "
          f"{subset['popularity'].min()}")


if __name__ == "__main__":
    main()
