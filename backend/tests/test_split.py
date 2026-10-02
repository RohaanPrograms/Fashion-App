import pandas as pd

from ml.split import split_by_date, trim_to_recent_months


def _transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "t_dat": pd.to_datetime(
                [
                    "2020-01-01",
                    "2020-06-01",
                    "2020-09-01",
                    "2020-09-15",
                    "2020-09-20",
                ]
            ),
            "customer_id": ["c1", "c1", "c2", "c2", "c3"],
            "article_id": ["a1", "a2", "a3", "a4", "a5"],
        }
    )


def test_trim_keeps_only_the_recent_window():
    result = trim_to_recent_months(_transactions(), months=1)

    # Latest date is 2020-09-20, so a 1-month window starts 2020-08-20.
    assert set(result["article_id"]) == {"a3", "a4", "a5"}


def test_split_puts_the_final_days_in_holdout():
    train, holdout = split_by_date(_transactions(), holdout_days=10)

    # Latest is 2020-09-20; cutoff is 2020-09-10.
    assert set(train["article_id"]) == {"a1", "a2", "a3"}
    assert set(holdout["article_id"]) == {"a4", "a5"}


def test_no_holdout_row_predates_any_train_row():
    """The whole point of a temporal split. A random split would train on a
    customer's later purchase and test on an earlier one, leaking the future
    into training and inflating every metric we report."""
    train, holdout = split_by_date(_transactions(), holdout_days=10)

    assert train["t_dat"].max() < holdout["t_dat"].min()


def test_split_is_exhaustive_and_disjoint():
    original = _transactions()
    train, holdout = split_by_date(original, holdout_days=10)

    assert len(train) + len(holdout) == len(original)
    assert set(train.index).isdisjoint(set(holdout.index))
