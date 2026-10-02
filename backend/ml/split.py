"""Stage 2 — trim the transaction window and split it by time.

A random split would put a customer's later purchase in training and an
earlier one in the test set: the model would have seen the future and every
metric would be inflated. Splitting on a date mirrors reality — you only ever
know the past.
"""

from __future__ import annotations

import pandas as pd


def trim_to_recent_months(
    transactions: pd.DataFrame, months: int, date_col: str = "t_dat"
) -> pd.DataFrame:
    """Keep only the most recent `months` of transactions.

    Measured back from the latest date in the data, not from today: the
    dataset is historical.
    """
    latest = transactions[date_col].max()
    cutoff = latest - pd.DateOffset(months=months)
    return transactions[transactions[date_col] > cutoff].copy()


def split_by_date(
    transactions: pd.DataFrame, holdout_days: int, date_col: str = "t_dat"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into (train, holdout) on a date boundary.

    Returns:
        train: everything up to and including the cutoff.
        holdout: the final `holdout_days`, never seen during training.
    """
    latest = transactions[date_col].max()
    cutoff = latest - pd.Timedelta(days=holdout_days)
    train = transactions[transactions[date_col] <= cutoff].copy()
    holdout = transactions[transactions[date_col] > cutoff].copy()
    return train, holdout
