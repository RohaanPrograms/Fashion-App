import pandas as pd

from ml.selection import count_training_window_purchases, select_catalog_subset


def _articles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "article_id": ["a1", "a2", "a3", "b1", "b2", "c1"],
            "product_group_name": [
                "Garment Upper body",
                "Garment Upper body",
                "Garment Upper body",
                "Shoes",
                "Shoes",
                "Underwear",
            ],
            "product_code": ["pA", "pA", "pB", "pC", "pD", "pE"],
        }
    )


def test_fills_each_quota_by_popularity_within_category():
    counts = pd.Series({"a1": 10, "a2": 50, "a3": 30, "b1": 5, "b2": 99, "c1": 100})

    result = select_catalog_subset(
        _articles(), counts, {"Garment Upper body": 2, "Shoes": 1}
    )

    tops = result[result["product_group_name"] == "Garment Upper body"]
    # The two most-bought tops, not the two most-bought articles overall.
    assert set(tops["article_id"]) == {"a2", "a3"}
    shoes = result[result["product_group_name"] == "Shoes"]
    assert set(shoes["article_id"]) == {"b2"}


def test_categories_without_a_quota_are_excluded():
    counts = pd.Series({"a1": 10, "a2": 50, "a3": 30, "b1": 5, "b2": 99, "c1": 100})

    result = select_catalog_subset(_articles(), counts, {"Shoes": 2})

    # c1 is the single most-bought article in the data but has no quota.
    assert "c1" not in set(result["article_id"])
    assert "Underwear" not in set(result["product_group_name"])


def test_popularity_column_is_attached():
    counts = pd.Series({"a1": 10, "a2": 50, "a3": 30, "b1": 5, "b2": 99, "c1": 100})

    result = select_catalog_subset(_articles(), counts, {"Shoes": 1})

    assert result.iloc[0]["popularity"] == 99


def test_articles_never_purchased_get_zero_and_rank_last():
    counts = pd.Series({"b2": 99})

    result = select_catalog_subset(_articles(), counts, {"Shoes": 2})

    assert list(result["article_id"]) == ["b2", "b1"]
    assert result.iloc[1]["popularity"] == 0


def test_quota_larger_than_available_takes_everything_available():
    counts = pd.Series({"b1": 5, "b2": 99})

    result = select_catalog_subset(_articles(), counts, {"Shoes": 50})

    assert len(result) == 2


def _dated(dates_and_articles: list[tuple[str, str]]) -> pd.DataFrame:
    dates, articles = zip(*dates_and_articles)
    return pd.DataFrame({"t_dat": pd.to_datetime(list(dates)), "article_id": list(articles)})


def test_training_window_counts_only_purchases_between_the_boundaries():
    # Latest date 2020-03-31 → holdout is after 2020-03-29 (2 days),
    # window starts after 2020-02-29 (1 month back from the latest date).
    transactions = _dated(
        [
            ("2020-01-15", "old"),        # before the window: ignored
            ("2020-02-29", "edge_start"), # exactly the start boundary: excluded
            ("2020-03-01", "inside"),
            ("2020-03-10", "inside"),
            ("2020-03-29", "edge_end"),   # last training day: included
            ("2020-03-31", "holdout"),    # in the holdout: excluded
        ]
    )

    counts = count_training_window_purchases(transactions, months=1, holdout_days=2)

    assert counts.to_dict() == {"inside": 2, "edge_end": 1}


def test_item_popular_only_before_the_window_is_not_selected():
    """The bug this guards against: an old best-seller with no purchases in the
    training window would be chosen, then have no ALS vector."""
    transactions = _dated(
        [("2019-06-01", "b1")] * 50          # big seller, but long ago
        + [("2020-03-15", "b2")] * 3         # modest, but within the window
        + [("2020-03-31", "a1")]             # pins the latest date
    )

    counts = count_training_window_purchases(transactions, months=1, holdout_days=2)
    result = select_catalog_subset(_articles(), counts, {"Shoes": 1})

    assert list(result["article_id"]) == ["b2"]
