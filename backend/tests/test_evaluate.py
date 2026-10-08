import numpy as np
import pandas as pd
import pytest

from ml.constants import COLD_START_LIKES
from ml.evaluate import (
    Scores,
    bootstrap_ci,
    build_eval_cases,
    compare,
    evaluate_model,
    evaluate_popularity,
    evaluate_random,
)
from ml.matrix import IndexMapping, build_interaction_matrix

NO_GROUPS = [None] * 5


def _holdout() -> pd.DataFrame:
    """One customer with five purchases, in order."""
    return pd.DataFrame(
        {
            "t_dat": pd.to_datetime(
                ["2020-09-16", "2020-09-17", "2020-09-18", "2020-09-19", "2020-09-20"]
            ),
            "customer_id": ["c1"] * 5,
            "article_id": ["a1", "a2", "a3", "a4", "a5"],
        }
    )


def _mapping():
    return build_interaction_matrix(_holdout())[1]


def _positions(mapping: IndexMapping, article_ids: list[str]) -> list[int]:
    return [mapping.article_position(article_id) for article_id in article_ids]


# --- building the simulated visitors -----------------------------------------


def test_seed_uses_the_earliest_purchases_and_targets_the_rest():
    cases = build_eval_cases(_holdout(), _mapping(), seed_likes=2)

    assert len(cases) == 1
    mapping = _mapping()
    assert cases[0].seed_positions == _positions(mapping, ["a1", "a2"])
    assert cases[0].target_positions == set(_positions(mapping, ["a3", "a4", "a5"]))


def test_seeds_are_the_earliest_even_when_the_file_is_not_in_date_order():
    shuffled = _holdout().iloc[[4, 2, 0, 3, 1]]

    cases = build_eval_cases(shuffled, _mapping(), seed_likes=2)

    assert cases[0].seed_positions == _positions(_mapping(), ["a1", "a2"])


def test_same_day_purchases_keep_their_file_order():
    """The data has dates but no times, so most baskets are all one day.

    A default (non-stable) sort reorders tied rows once a table reaches ~50
    rows — on the real holdout it moved 177,355 of 177,357 — which would pick
    each visitor's seeds from an arbitrary shuffle of their basket.
    """
    article_ids = [f"a{i:03d}" for i in range(60)]
    holdout = pd.DataFrame(
        {
            "t_dat": pd.to_datetime(["2020-09-10"] * 60),
            "customer_id": ["c1"] * 60,
            "article_id": article_ids,
        }
    )
    mapping = IndexMapping(customer_ids=["c1"], article_ids=article_ids)

    cases = build_eval_cases(holdout, mapping, seed_likes=3)

    assert cases[0].seed_positions == [0, 1, 2]


def test_customers_without_enough_purchases_are_skipped():
    thin = _holdout().head(2)

    cases = build_eval_cases(thin, build_interaction_matrix(thin)[1], seed_likes=3)

    assert cases == []


def test_a_repeat_purchase_is_not_a_second_thing_to_predict():
    holdout = _holdout()
    holdout.loc[1, "article_id"] = "a1"  # a1, a1, a3, a4, a5

    cases = build_eval_cases(holdout, _mapping(), seed_likes=2)

    mapping = _mapping()
    assert cases[0].seed_positions == _positions(mapping, ["a1", "a3"])
    assert cases[0].target_positions == set(_positions(mapping, ["a4", "a5"]))


def test_articles_the_model_has_no_vector_for_are_dropped():
    holdout = pd.concat(
        [
            _holdout(),
            pd.DataFrame(
                {
                    "t_dat": pd.to_datetime(["2020-09-15"]),
                    "customer_id": ["c1"],
                    "article_id": ["never_trained"],
                }
            ),
        ]
    )

    cases = build_eval_cases(holdout, _mapping(), seed_likes=2)

    assert cases[0].seed_positions == _positions(_mapping(), ["a1", "a2"])


def test_customer_ids_stored_as_a_pandas_category_work():
    """The real holdout.parquet stores customer_id as a category. Categories
    can include customers with no rows left after filtering, and pandas warns
    about how it groups them unless told explicitly."""
    holdout = _holdout()
    holdout["customer_id"] = pd.Categorical(
        holdout["customer_id"], categories=["c0_no_rows", "c1"]
    )

    cases = build_eval_cases(holdout, _mapping(), seed_likes=2)

    assert len(cases) == 1


def test_seed_items_never_appear_in_targets():
    """If a seed leaked into the targets the model would score for predicting
    something it was literally shown, inflating every number."""
    cases = build_eval_cases(_holdout(), _mapping(), seed_likes=2)

    assert set(cases[0].seed_positions).isdisjoint(cases[0].target_positions)


def test_default_seed_size_matches_the_shared_constant():
    """The evaluation and the live feed must agree on this, or the README's
    headline number describes a different system than the one that ships."""
    cases = build_eval_cases(_holdout(), _mapping())

    assert len(cases[0].seed_positions) == COLD_START_LIKES


# --- the model and the baselines ---------------------------------------------


def test_a_model_that_knows_the_answer_scores_perfectly():
    """Vectors arranged so the targets are the nearest neighbours of the seeds."""
    mapping = _mapping()
    vectors = np.zeros((5, 2))
    for article_id in ["a1", "a2", "a3", "a4", "a5"]:
        vectors[mapping.article_position(article_id)] = [1.0, 0.0]

    cases = build_eval_cases(_holdout(), mapping, seed_likes=2)
    result = evaluate_model(cases, vectors, k=5, groups=NO_GROUPS)

    assert result.recall.mean() == 1.0
    assert result.n_users == 1


def _colourway_setup():
    """A visitor likes `s` and later buys `t`. Two colourways of one design
    (`v1`, `v2`, both group "g") sit between them in every ranking."""
    article_ids = ["s", "t", "v1", "v2", "x"]
    mapping = IndexMapping(customer_ids=["c1"], article_ids=article_ids)
    holdout = pd.DataFrame(
        {
            "t_dat": pd.to_datetime(["2020-09-16", "2020-09-17"]),
            "customer_id": ["c1", "c1"],
            "article_id": ["s", "t"],
        }
    )
    cases = build_eval_cases(holdout, mapping, seed_likes=1)
    groups = ["gs", "gt", "g", "g", "gx"]
    return mapping, cases, groups


def test_model_shows_one_colourway_per_design_as_the_feed_does():
    mapping, cases, groups = _colourway_setup()
    vectors = np.zeros((5, 2))
    for article_id, vector in [
        ("s", [1.0, 0.0]),
        ("v1", [0.99, 0.10]),
        ("v2", [0.98, 0.15]),
        ("t", [0.90, 0.40]),
        ("x", [0.0, 1.0]),
    ]:
        vectors[mapping.article_position(article_id)] = vector

    deduped = evaluate_model(cases, vectors, k=2, groups=groups)
    not_deduped = evaluate_model(cases, vectors, k=2, groups=NO_GROUPS)

    # Without dedupe both slots go to the same design and t is pushed out.
    assert not_deduped.recall.mean() == 0.0
    assert deduped.recall.mean() == 1.0


def test_popularity_baseline_recommends_the_most_popular_unseen_items():
    mapping = _mapping()
    popularity = np.zeros(5)
    for article_id, score in [("a3", 100.0), ("a4", 90.0), ("a5", 80.0)]:
        popularity[mapping.article_position(article_id)] = score

    cases = build_eval_cases(_holdout(), mapping, seed_likes=2)
    result = evaluate_popularity(cases, popularity, k=3, groups=NO_GROUPS)

    assert result.recall.mean() == 1.0


def test_popularity_baseline_also_shows_one_colourway_per_design():
    mapping, cases, groups = _colourway_setup()
    popularity = np.zeros(5)
    for article_id, score in [("v1", 100.0), ("v2", 90.0), ("t", 80.0)]:
        popularity[mapping.article_position(article_id)] = score

    deduped = evaluate_popularity(cases, popularity, k=2, groups=groups)
    not_deduped = evaluate_popularity(cases, popularity, k=2, groups=NO_GROUPS)

    assert not_deduped.recall.mean() == 0.0
    assert deduped.recall.mean() == 1.0


def test_random_baseline_runs_and_stays_in_range():
    cases = build_eval_cases(_holdout(), _mapping(), seed_likes=2)

    result = evaluate_random(
        cases, n_items=5, k=3, groups=NO_GROUPS, rng=np.random.default_rng(1234)
    )

    assert 0.0 <= result.recall.mean() <= 1.0


def test_scores_hold_one_entry_per_visitor_with_hand_computed_values():
    """Targets {a3, a4, a5}; a perfectly wrong-then-right ranking checked by hand."""
    mapping = _mapping()
    popularity = np.zeros(5)
    # After excluding the seeds a1, a2 the order is a3 (hit), a4 (hit), a5 (hit).
    for article_id, score in [("a3", 3.0), ("a4", 2.0), ("a5", 1.0)]:
        popularity[mapping.article_position(article_id)] = score
    cases = build_eval_cases(_holdout(), mapping, seed_likes=2)

    result = evaluate_popularity(cases, popularity, k=2, groups=NO_GROUPS)

    # Top 2 = a3, a4: recall 2/3; AP = (1/1 + 2/2) / min(2, 3) = 1.0
    assert result.recall.tolist() == pytest.approx([2 / 3])
    assert result.average_precision.tolist() == pytest.approx([1.0])


# --- new designs only --------------------------------------------------------


def _new_design_setup(groups: list[str | None]):
    """Visitor likes `s`, then buys `t` and `u`. Vectors rank t, then u."""
    article_ids = ["s", "t", "u", "x"]
    mapping = IndexMapping(customer_ids=["c1"], article_ids=article_ids)
    holdout = pd.DataFrame(
        {
            "t_dat": pd.to_datetime(["2020-09-16", "2020-09-17", "2020-09-18"]),
            "customer_id": ["c1"] * 3,
            "article_id": ["s", "t", "u"],
        }
    )
    vectors = np.array([[1.0, 0.0], [0.9, 0.1], [0.8, 0.2], [0.0, 1.0]])
    cases = build_eval_cases(holdout, mapping, seed_likes=1)
    return evaluate_model(cases, vectors, k=1, groups=groups)


def test_new_design_recall_ignores_other_colours_of_a_liked_design():
    # t is another colour of the liked s; u is a new design. The single slot
    # goes to t: a hit for plain recall, but not a new design.
    scores = _new_design_setup(["g", "g", "gu", "gx"])

    assert scores.recall.tolist() == pytest.approx([0.5])
    assert scores.new_design_recall.tolist() == pytest.approx([0.0])


def test_new_design_recall_counts_hits_on_new_designs():
    scores = _new_design_setup(["gs", "gt", "gu", "gx"])

    assert scores.new_design_recall.tolist() == pytest.approx([0.5])


def test_visitor_who_only_bought_liked_designs_has_no_new_design_score():
    scores = _new_design_setup(["g", "g", "g", "gx"])

    assert np.isnan(scores.new_design_recall[0])


def test_missing_designs_never_count_as_the_same_design():
    """A missing product_code means "unknown", not "same as every other unknown"."""
    scores = _new_design_setup([None, None, float("nan"), "gx"])

    assert scores.new_design_recall.tolist() == pytest.approx([0.5])


# --- error bars --------------------------------------------------------------


def test_bootstrap_of_identical_values_has_no_width():
    assert bootstrap_ci(np.full(100, 0.25)) == pytest.approx([0.25, 0.25])


def test_bootstrap_width_matches_textbook_for_a_coin_flip():
    """1,000 values, half 0 and half 1: the textbook 95% interval for the mean
    is 0.5 +/- 1.96 * sqrt(0.25 / 1000) = 0.469 to 0.531."""
    values = np.array([0.0, 1.0] * 500)

    low, high = bootstrap_ci(values)

    assert low == pytest.approx(0.469, abs=0.006)
    assert high == pytest.approx(0.531, abs=0.006)


def test_bootstrap_is_reproducible():
    values = np.random.default_rng(0).random(500)

    assert bootstrap_ci(values, seed=7) == bootstrap_ci(values, seed=7)


def test_bootstrap_of_nothing_is_an_error():
    with pytest.raises(ValueError):
        bootstrap_ci(np.array([]))


def _scores(values, new_design=None) -> Scores:
    values = np.asarray(values, dtype=float)
    return Scores(
        recall=values,
        average_precision=values,
        new_design_recall=values if new_design is None else np.asarray(new_design),
    )


def test_summary_reports_means_intervals_and_count():
    scores = Scores(
        recall=np.array([1.0, 0.0, 0.5, 0.5]),
        average_precision=np.array([0.5, 0.0, 0.25, 0.25]),
        new_design_recall=np.array([1.0, np.nan, 0.0, np.nan]),
    )

    summary = scores.summary()

    assert summary["recall_at_k"] == pytest.approx(0.5)
    assert summary["map_at_k"] == pytest.approx(0.25)
    assert summary["n_users"] == 4
    low, high = summary["recall_ci95"]
    assert low <= 0.5 <= high
    # Visitors with no new-design purchases are left out, not scored as 0.
    assert summary["new_design_recall_at_k"] == pytest.approx(0.5)
    assert summary["n_users_new_designs"] == 2


def test_compare_is_paired_visitor_by_visitor():
    """Same visitors, two recommenders: the gap is measured per visitor.

    a beats b by exactly 0.5 for every visitor, so the gap's interval has no
    width — even though each score on its own varies a lot between visitors.
    """
    b_recall = np.array([0.0, 0.25, 0.5, 0.1])
    a = _scores(b_recall + 0.5)
    b = _scores(b_recall)

    result = compare(a, b)

    assert result["recall_diff"] == pytest.approx(0.5)
    assert result["recall_diff_ci95"] == pytest.approx([0.5, 0.5])
    assert result["map_diff"] == pytest.approx(0.5)
    assert result["new_design_recall_diff"] == pytest.approx(0.5)


def test_compare_new_designs_skips_visitors_without_a_score():
    a = _scores([1.0, 1.0, 1.0], new_design=[1.0, np.nan, 0.5])
    b = _scores([0.0, 0.0, 0.0], new_design=[0.5, np.nan, 0.0])

    result = compare(a, b)

    assert result["new_design_recall_diff"] == pytest.approx(0.5)


def test_compare_refuses_scores_from_different_visitors():
    a = _scores(np.zeros(3))
    b = _scores(np.zeros(4))

    with pytest.raises(ValueError):
        compare(a, b)
