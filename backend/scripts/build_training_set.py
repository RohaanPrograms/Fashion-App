"""Stage 2 CLI — build the train and holdout transaction files.

    cd backend
    python -m scripts.build_training_set --data-dir ../data/hm \
        --subset ../data/subset.csv --out-dir ../data
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ml.constants import HOLDOUT_DAYS, TRAINING_WINDOW_MONTHS
from ml.split import split_by_date, trim_to_recent_months
from scripts.hm_data import article_ids_to_int, article_ids_to_str, load_transactions


def keep_catalog_articles(transactions: pd.DataFrame, catalog_ids: pd.Series) -> pd.DataFrame:
    kept = transactions[transactions["article_id"].isin(catalog_ids)].copy()
    kept["article_id"] = article_ids_to_str(kept["article_id"])
    kept["customer_id"] = kept["customer_id"].cat.remove_unused_categories()
    return kept


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--subset", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    catalog_ids = article_ids_to_int(
        pd.read_csv(args.subset, dtype={"article_id": str})["article_id"]
    )
    transactions = load_transactions(
        args.data_dir / "transactions_train.csv", with_customers=True
    )

    # Split BEFORE filtering to the catalog: the cutoff comes from the latest
    # date in the full data, matching the window used to select the catalog.
    recent = trim_to_recent_months(transactions, TRAINING_WINDOW_MONTHS)
    del transactions
    train, holdout = split_by_date(recent, HOLDOUT_DAYS)
    del recent

    train = keep_catalog_articles(train, catalog_ids)
    holdout = keep_catalog_articles(holdout, catalog_ids)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    train.to_parquet(args.out_dir / "train.parquet", index=False)
    holdout.to_parquet(args.out_dir / "holdout.parquet", index=False)

    print(f"train:   {len(train):>9,} rows, {train['t_dat'].min().date()} "
          f"to {train['t_dat'].max().date()}, {train['customer_id'].nunique():,} customers")
    print(f"holdout: {len(holdout):>9,} rows, {holdout['t_dat'].min().date()} "
          f"to {holdout['t_dat'].max().date()}, {holdout['customer_id'].nunique():,} customers")
    per_customer = holdout.groupby("customer_id", observed=True).size()
    print(f"holdout customers with 4+ purchases (usable for evaluation): "
          f"{(per_customer >= 4).sum():,}")


if __name__ == "__main__":
    main()
