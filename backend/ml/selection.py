"""Stage 1 — choose which articles make up the demo catalog.

ALS learns an item's vector purely from who bought it *in the training window*,
so popularity is counted inside that window only. Counting all two years would
pick old best-sellers with no recent purchases, which would get no vector.

Popularity alone would also hand us thousands of tops and almost no shoes, so
each category gets its own quota, filled by popularity within that category.
See spec section 4, Stage 1.
"""

from __future__ import annotations

import pandas as pd

from ml.split import split_by_date, trim_to_recent_months


def count_training_window_purchases(
    transactions: pd.DataFrame,
    months: int,
    holdout_days: int,
    date_col: str = "t_dat",
) -> pd.Series:
    """Purchases per article within the training window, indexed by article_id.

    Reuses ml/split.py so the window is cut exactly where training data is.
    """
    recent = trim_to_recent_months(transactions, months, date_col)
    train, _holdout = split_by_date(recent, holdout_days, date_col)
    return train["article_id"].value_counts()


def select_catalog_subset(
    articles: pd.DataFrame,
    purchase_counts: pd.Series,
    quotas: dict[str, int],
) -> pd.DataFrame:
    """Pick the catalog subset.

    Args:
        articles: rows from articles.csv. Must contain `article_id` and
            `product_group_name`.
        purchase_counts: index is article_id, value is how many times it was
            bought. Articles missing from this series are treated as zero
            rather than dropped, so a quota can still be filled from a thin
            category.
        quotas: category name -> how many articles to take. Categories absent
            from this mapping are excluded from the catalog entirely.

    Returns:
        The selected rows, with an integer `popularity` column added, sorted
        by popularity descending.
    """
    enriched = articles.copy()
    enriched["popularity"] = (
        enriched["article_id"].map(purchase_counts).fillna(0).astype(int)
    )

    selected: list[pd.DataFrame] = []
    for category, quota in quotas.items():
        in_category = enriched[enriched["product_group_name"] == category]
        # Stable sort: ties keep file order, so re-runs pick identical articles.
        ranked = in_category.sort_values("popularity", ascending=False, kind="stable")
        selected.append(ranked.head(quota))

    if not selected:
        return enriched.iloc[0:0].copy()

    return (
        pd.concat(selected)
        .sort_values("popularity", ascending=False, kind="stable")
        .reset_index(drop=True)
    )
