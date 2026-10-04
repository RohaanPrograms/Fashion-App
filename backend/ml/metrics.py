"""Ranking metrics, hand-tested.

WHY THESE TESTS MATTER MORE THAN MOST
-------------------------------------
Every number in the README comes out of this file. A bug here does not crash
anything — it produces a plausible-looking score that is simply wrong, makes
the factor-tuning table meaningless, and would have you telling an interviewer
something false. Testing the metric is testing the claim.
"""

from __future__ import annotations

from typing import Callable, Sequence


def recall_at_k(
    recommended: Sequence[int], relevant: set[int], k: int
) -> float:
    """What share of the user's actual purchases appear in the top k?"""
    if not relevant:
        return 0.0
    top_k = set(recommended[:k])
    return len(top_k & relevant) / len(relevant)


def average_precision_at_k(
    recommended: Sequence[int], relevant: set[int], k: int
) -> float:
    """Average precision — like recall, but rewards hits nearer the top.

    Each hit contributes the precision at the position it was found; the sum is
    divided by min(k, number of relevant items), which is the maximum number of
    hits that could possibly fit in k slots.

    An item recommended twice counts as a hit once, as in the official Kaggle
    scorer; otherwise the score could exceed 1.
    """
    if not relevant:
        return 0.0

    found: set[int] = set()
    precision_sum = 0.0
    for position, item in enumerate(recommended[:k], start=1):
        if item in relevant and item not in found:
            found.add(item)
            precision_sum += len(found) / position

    denominator = min(k, len(relevant))
    return precision_sum / denominator if denominator else 0.0


def map_at_k(
    all_recommended: Sequence[Sequence[int]],
    all_relevant: Sequence[set[int]],
    k: int,
) -> float:
    """Mean average precision across users."""
    return _mean_over_users(average_precision_at_k, all_recommended, all_relevant, k)


def mean_recall_at_k(
    all_recommended: Sequence[Sequence[int]],
    all_relevant: Sequence[set[int]],
    k: int,
) -> float:
    """Mean recall@k across users."""
    return _mean_over_users(recall_at_k, all_recommended, all_relevant, k)


def _mean_over_users(
    metric: Callable[[Sequence[int], set[int], int], float],
    all_recommended: Sequence[Sequence[int]],
    all_relevant: Sequence[set[int]],
    k: int,
) -> float:
    # len() rather than `not all_recommended`: the latter raises on numpy arrays.
    # strict=True: the two lists are paired user by user, and a length mismatch
    # would otherwise be truncated silently and score users against the wrong
    # purchases.
    if len(all_recommended) == 0 and len(all_relevant) == 0:
        return 0.0
    scores = [
        metric(recommended, relevant, k)
        for recommended, relevant in zip(all_recommended, all_relevant, strict=True)
    ]
    return sum(scores) / len(scores)
