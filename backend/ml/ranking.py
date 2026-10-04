"""Pure ranking functions — no database, no network, no globals.

WHY THIS IS A SEPARATE MODULE
-----------------------------
The offline evaluation and the live feed endpoint must rank items using
exactly the same code, or the number in the README describes a system that was
never shipped. Keeping it pure also means these functions are testable against
hand-computed answers, which matters because ranking bugs are silent: a
reversed sort does not crash, it just serves worse clothes forever.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ml.constants import DISLIKE_WEIGHT


def build_style_vector(
    liked: np.ndarray,
    disliked: np.ndarray | None = None,
    dislike_weight: float = DISLIKE_WEIGHT,
) -> np.ndarray:
    """Average the liked vectors, then subtract the disliked ones at a discount.

    Args:
        liked: shape (n_liked, n_factors). Must not be empty.
        disliked: shape (n_disliked, n_factors), or None.
        dislike_weight: how strongly dislikes count. An unvalidated heuristic
            — the training data contains no dislikes.

    Raises:
        ValueError: if `liked` is empty. Callers check COLD_START_LIKES first;
            failing loudly here beats returning a zero vector that would rank
            every item identically without anyone noticing.
    """
    if liked.shape[0] == 0:
        raise ValueError("build_style_vector needs at least one liked item")

    vector = liked.mean(axis=0)
    if disliked is not None and disliked.shape[0] > 0:
        vector = vector - dislike_weight * disliked.mean(axis=0)
    return vector


def rank_by_similarity(
    style_vector: np.ndarray, item_vectors: np.ndarray
) -> np.ndarray:
    """Rank every item by cosine similarity to the style vector, best first.

    Cosine similarity compares direction, not magnitude, so a style vector
    built from 20 likes ranks identically to one built from 2.

    Returns:
        Item positions (indices into item_vectors), best first.
    """
    item_norms = np.linalg.norm(item_vectors, axis=1)
    style_norm = np.linalg.norm(style_vector)
    # Guard against divide-by-zero for any all-zero vector; such an item scores
    # 0 against everything, which is the correct "no information" answer.
    denominator = np.where(item_norms == 0, 1.0, item_norms) * max(style_norm, 1e-12)
    scores = (item_vectors @ style_vector) / denominator
    scores = np.where(item_norms == 0, -np.inf, scores)
    return np.argsort(-scores, kind="stable")


def exclude_positions(ranked: np.ndarray, excluded: set[int]) -> np.ndarray:
    """Drop positions the user has already seen, preserving rank order."""
    if not excluded:
        return ranked
    return ranked[~np.isin(ranked, list(excluded))]


def dedupe_by_group(
    ranked: np.ndarray, groups: Sequence[str | None]
) -> np.ndarray:
    """Keep only the best-ranked item from each group.

    H&M sells one garment as several articles, one per colourway, and their
    vectors are near-identical — without this the feed shows the same jumper
    eight times.

    Items with a missing group are each treated as unique: a null means
    "unknown", not "the same as every other null". pandas writes a missing
    value as NaN rather than None, so both count as missing.
    """
    seen: set[str] = set()
    kept: list[int] = []
    for position in ranked:
        group = groups[position]
        # NaN is the only value not equal to itself.
        if group is None or group != group:
            kept.append(int(position))
            continue
        if group in seen:
            continue
        seen.add(group)
        kept.append(int(position))
    return np.array(kept, dtype=int)


def split_exploration(
    ranked: np.ndarray,
    n_total: int,
    n_explore: int,
    pool_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Take the top items, plus a few sampled from further down the ranking.

    Taking the top N every time makes the feed converge on one narrow lane and
    never escape it. Sampling a couple from a wider pool keeps it breathing.
    This is a deliberately crude stand-in for proper filter-bubble work.

    If the ranking is shorter than `n_total`, everything available is returned.
    """
    if len(ranked) <= n_total:
        return ranked

    n_top = n_total - n_explore
    top = ranked[:n_top]

    # The pool always reaches past the batch, so it holds at least n_explore
    # items and the batch comes back full even if pool_size is set too small.
    pool = ranked[n_top : max(pool_size, n_total)]
    explored = rng.choice(pool, size=n_explore, replace=False)
    return np.concatenate([top, explored])
