"""Cold-start evaluation — measuring the path the app actually serves.

WHY NOT THE CONVENTIONAL EVALUATION
-----------------------------------
ALS produces user vectors as well as item vectors, and the textbook evaluation
scores items against a customer's user vector. This project does not, because
the app has no such customers: every visitor is a stranger whose taste is built
by averaging the vectors of items they swiped right on.

Scoring the textbook way would measure a code path that never ships. So the
harness below simulates a visitor instead: take a held-out customer, treat
their first COLD_START_LIKES purchases as swipes, build the style vector
exactly as the live feed does, and see whether the rest of their basket comes
back near the top.

AS SERVED, MINUS EXPLORATION
----------------------------
Every recommender here — the model and both baselines — goes through the same
steps as the feed: drop what the visitor already liked, then keep one
colourway per design. The feed's two random exploration slots are left out on
purpose: they trade accuracy for variety by design, and would only add noise
to the comparison.

NEW DESIGNS ONLY
----------------
Recommending another colour of a design the visitor just liked is a correct
guess, but an easy one. new_design_recall scores only purchases of designs the
visitor had not liked, so the headline can say how much of the win is style
rather than "same item, other colour". Visitors whose every purchase was
another colour of a liked design have nothing to score there and are left out
(NaN), not counted as 0.

ERROR BARS
----------
Scores are kept per visitor so they can be bootstrapped: re-drawn at random
(with replacement) many times to see how much the average moves depending on
which visitors happened to be in the test. Comparisons are paired — both
recommenders are scored on the same visitors, so the gap is measured visitor
by visitor, which is far less noisy than comparing two separate averages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

from ml.constants import COLD_START_LIKES, RANDOM_SEED
from ml.matrix import IndexMapping
from ml.metrics import average_precision_at_k, recall_at_k
from ml.ranking import (
    build_style_vector,
    dedupe_by_group,
    exclude_positions,
    rank_by_similarity,
)

BOOTSTRAP_RESAMPLES = 1000
CONFIDENCE = 0.95


@dataclass(frozen=True)
class EvalCase:
    """One simulated visitor."""

    seed_positions: list[int]
    target_positions: set[int]


def build_eval_cases(
    holdout: pd.DataFrame,
    mapping: IndexMapping,
    seed_likes: int = COLD_START_LIKES,
) -> list[EvalCase]:
    """Turn held-out transactions into simulated cold-start visitors.

    Purchases of articles the model has no vector for are dropped. Customers
    with `seed_likes` or fewer distinct purchases left are skipped — there
    would be nothing to predict.
    """
    known = holdout[holdout["article_id"].isin(set(mapping.article_ids))]
    # Stable: the data has dates but no times, so same-day purchases must keep
    # their file order. A default sort shuffles tied rows on large tables.
    ordered_rows = known.sort_values("t_dat", kind="stable")

    cases: list[EvalCase] = []
    # observed=True: customer_id may be a category that still lists customers
    # whose rows were all filtered out above.
    for _, group in ordered_rows.groupby("customer_id", sort=True, observed=True):
        # Deduplicate keeping purchase order (dicts preserve insertion order):
        # a repeat buy is not a second thing to predict.
        ordered = list(
            dict.fromkeys(mapping.article_position(a) for a in group["article_id"])
        )
        if len(ordered) <= seed_likes:
            continue
        cases.append(
            EvalCase(
                seed_positions=ordered[:seed_likes],
                target_positions=set(ordered[seed_likes:]),
            )
        )
    return cases


@dataclass(frozen=True)
class Scores:
    """Per-visitor scores, one entry per EvalCase, in the same order."""

    recall: np.ndarray
    average_precision: np.ndarray
    # NaN for visitors with no purchases of new designs (see module docstring).
    new_design_recall: np.ndarray

    @property
    def n_users(self) -> int:
        return len(self.recall)

    def summary(
        self, n_resamples: int = BOOTSTRAP_RESAMPLES, seed: int = RANDOM_SEED
    ) -> dict:
        """Averages (recall@k, MAP@k, new-design recall@k) with 95% intervals."""
        new_design = self.new_design_recall[~np.isnan(self.new_design_recall)]
        return {
            "recall_at_k": float(self.recall.mean()),
            "recall_ci95": bootstrap_ci(self.recall, n_resamples, seed),
            "map_at_k": float(self.average_precision.mean()),
            "map_ci95": bootstrap_ci(self.average_precision, n_resamples, seed),
            "n_users": self.n_users,
            "new_design_recall_at_k": float(new_design.mean()),
            "new_design_recall_ci95": bootstrap_ci(new_design, n_resamples, seed),
            "n_users_new_designs": len(new_design),
        }


def bootstrap_ci(
    values: np.ndarray,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = RANDOM_SEED,
) -> list[float]:
    """95% interval for the mean of `values`, by bootstrap.

    Draw len(values) values at random with replacement, average them, repeat
    n_resamples times; the middle 95% of those averages is the interval.
    Returned as a list so it drops straight into JSON.
    """
    if len(values) == 0:
        raise ValueError("cannot bootstrap an empty set of scores")
    rng = np.random.default_rng(seed)
    means = np.array(
        [values[rng.integers(0, len(values), len(values))].mean() for _ in range(n_resamples)]
    )
    tail = (1 - CONFIDENCE) / 2 * 100
    low, high = np.percentile(means, [tail, 100 - tail])
    return [float(low), float(high)]


def compare(
    a: Scores, b: Scores, n_resamples: int = BOOTSTRAP_RESAMPLES, seed: int = RANDOM_SEED
) -> dict:
    """How far `a` is ahead of `b`, measured visitor by visitor.

    If the interval on a difference is entirely above 0, `a` is genuinely
    better on this data rather than ahead by the luck of which visitors were
    drawn.
    """
    if a.n_users != b.n_users:
        raise ValueError("compare needs both recommenders scored on the same visitors")
    recall_gap = a.recall - b.recall
    map_gap = a.average_precision - b.average_precision
    new_design_gap = a.new_design_recall - b.new_design_recall
    new_design_gap = new_design_gap[~np.isnan(new_design_gap)]
    return {
        "recall_diff": float(recall_gap.mean()),
        "recall_diff_ci95": bootstrap_ci(recall_gap, n_resamples, seed),
        "map_diff": float(map_gap.mean()),
        "map_diff_ci95": bootstrap_ci(map_gap, n_resamples, seed),
        "new_design_recall_diff": float(new_design_gap.mean()),
        "new_design_recall_diff_ci95": bootstrap_ci(new_design_gap, n_resamples, seed),
    }


def _serve(
    ranked: np.ndarray, case: EvalCase, groups: Sequence[str | None], k: int
) -> list[int]:
    """What the feed would show: unseen items, one colourway per design, top k."""
    ranked = exclude_positions(ranked, set(case.seed_positions))
    ranked = dedupe_by_group(ranked, groups)
    return [int(position) for position in ranked[:k]]


def _is_missing(group) -> bool:
    # NaN is the only value not equal to itself.
    return group is None or group != group


def _new_design_targets(case: EvalCase, groups: Sequence[str | None]) -> set[int]:
    """Targets whose design the visitor had not liked. A missing design never
    matches anything: "unknown" is not "the same as every other unknown"."""
    liked = {groups[p] for p in case.seed_positions if not _is_missing(groups[p])}
    return {
        p
        for p in case.target_positions
        if _is_missing(groups[p]) or groups[p] not in liked
    }


def _score(
    recommendations: list[list[int]],
    cases: list[EvalCase],
    k: int,
    groups: Sequence[str | None],
) -> Scores:
    pairs = list(zip(recommendations, cases, strict=True))
    new_design = []
    for recs, case in pairs:
        targets = _new_design_targets(case, groups)
        new_design.append(recall_at_k(recs, targets, k) if targets else np.nan)
    return Scores(
        recall=np.array(
            [recall_at_k(recs, case.target_positions, k) for recs, case in pairs]
        ),
        average_precision=np.array(
            [average_precision_at_k(recs, case.target_positions, k) for recs, case in pairs]
        ),
        new_design_recall=np.array(new_design, dtype=float),
    )


def evaluate_model(
    cases: list[EvalCase],
    item_vectors: np.ndarray,
    k: int,
    groups: Sequence[str | None],
) -> Scores:
    """Score the recommender on the simulated cold-start path.

    `groups[i]` is the design (product_code) of item i; use None for "unknown".
    """
    recommendations = []
    for case in cases:
        style = build_style_vector(item_vectors[case.seed_positions])
        ranked = rank_by_similarity(style, item_vectors)
        recommendations.append(_serve(ranked, case, groups, k))
    return _score(recommendations, cases, k, groups)


def evaluate_popularity(
    cases: list[EvalCase],
    popularity_by_position: np.ndarray,
    k: int,
    groups: Sequence[str | None],
) -> Scores:
    """The baseline that matters: recommend the best sellers to everyone.

    Popularity is genuinely strong in fashion. If the model only edges past
    this, that is the finding and it gets reported as such.
    """
    ranked_once = np.argsort(-popularity_by_position, kind="stable")
    recommendations = [_serve(ranked_once, case, groups, k) for case in cases]
    return _score(recommendations, cases, k, groups)


def evaluate_random(
    cases: list[EvalCase],
    n_items: int,
    k: int,
    groups: Sequence[str | None],
    rng: np.random.Generator,
) -> Scores:
    """Sanity check. Failing to beat this means something is broken."""
    recommendations = [
        _serve(rng.permutation(n_items), case, groups, k) for case in cases
    ]
    return _score(recommendations, cases, k, groups)
