"""Memory-efficient loading of the H&M transactions file, shared by the scripts.

Read as text, 31.8M rows of 64-character customer IDs and 10-digit article IDs
need ~6 GB of RAM. Read as below, the same table is ~0.6 GB: article IDs as
integers, and dates and customer IDs as categoricals (each distinct value
stored once, every row holding a small code pointing at it).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# article_id is 10 digits with a leading zero ("0108775015").
ARTICLE_ID_WIDTH = 10


def load_transactions(path: Path, with_customers: bool = False) -> pd.DataFrame:
    """Read t_dat (as dates) and article_id (as int64), plus customer_id if asked."""
    dtypes = {"t_dat": "category", "article_id": "int64"}
    if with_customers:
        dtypes["customer_id"] = "category"

    transactions = pd.read_csv(path, usecols=list(dtypes), dtype=dtypes)

    # ~730 distinct dates: parse each once, then spread back out by code.
    dates = transactions["t_dat"]
    transactions["t_dat"] = pd.to_datetime(dates.cat.categories)[dates.cat.codes]
    return transactions


def article_ids_to_str(ids: pd.Series | pd.Index) -> pd.Series | pd.Index:
    """Restore the leading zero lost by reading IDs as integers."""
    return ids.astype(str).str.zfill(ARTICLE_ID_WIDTH)


def article_ids_to_int(ids: pd.Series) -> pd.Series:
    return ids.astype("int64")
