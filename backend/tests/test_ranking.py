import numpy as np
import pytest

from ml.constants import DISLIKE_WEIGHT
from ml.ranking import (
    build_style_vector,
    dedupe_by_group,
    exclude_positions,
    rank_by_similarity,
    split_exploration,
)


def test_style_vector_of_likes_is_their_mean():
    liked = np.array([[1.0, 0.0], [0.0, 1.0]])

    result = build_style_vector(liked)

    assert np.allclose(result, [0.5, 0.5])


def test_dislikes_are_subtracted_at_the_configured_weight():
    liked = np.array([[1.0, 0.0]])
    disliked = np.array([[0.0, 1.0]])

    result = build_style_vector(liked, disliked, dislike_weight=0.3)

    # [1, 0] - 0.3 * [0, 1]
    assert np.allclose(result, [1.0, -0.3])


def test_default_dislike_weight_comes_from_the_shared_constant():
    """The feed and the evaluation must weigh dislikes identically."""
    liked = np.array([[1.0, 0.0]])
    disliked = np.array([[0.0, 1.0]])

    result = build_style_vector(liked, disliked)

    assert np.allclose(result, [1.0, -DISLIKE_WEIGHT])


def test_style_vector_with_no_likes_raises():
    """Callers must check COLD_START_LIKES first. Returning a zero vector here
    would silently rank everything identically instead of failing loudly."""
    with pytest.raises(ValueError):
        build_style_vector(np.empty((0, 2)))


def test_ranking_puts_the_most_similar_item_first(item_vectors):
    style = np.array([1.0, 0.0])  # pure "casual"

    ranked = rank_by_similarity(style, item_vectors)

    assert ranked[0] == 0     # exact match
    assert ranked[1] == 1     # near match
    assert ranked[-1] == 2    # orthogonal


def test_ranking_ignores_magnitude_and_compares_direction(item_vectors):
    """Cosine similarity measures angle, not length: a style vector built from
    ten likes must rank the same as one built from two."""
    short = rank_by_similarity(np.array([1.0, 0.0]), item_vectors)
    long = rank_by_similarity(np.array([50.0, 0.0]), item_vectors)

    assert list(short) == list(long)


def test_excluded_positions_are_removed_and_order_is_kept():
    ranked = np.array([3, 1, 0, 2])

    result = exclude_positions(ranked, {1, 2})

    assert list(result) == [3, 0]


def test_dedupe_keeps_only_the_best_ranked_item_per_group(product_groups):
    # Items 0 and 1 are both group "A"; 0 is ranked higher.
    ranked = np.array([0, 1, 2, 3])

    result = dedupe_by_group(ranked, product_groups)

    assert list(result) == [0, 2, 3]


def test_dedupe_treats_missing_group_as_its_own_group():
    ranked = np.array([0, 1, 2])
    groups = [None, None, "A"]

    result = dedupe_by_group(ranked, groups)

    # Nulls must not collapse into one another — they are unknown, not equal.
    assert list(result) == [0, 1, 2]


def test_dedupe_treats_nan_like_none():
    """pandas writes a missing value as NaN rather than None."""
    nan = float("nan")
    ranked = np.array([0, 1, 2, 3])
    groups = [nan, nan, "A", "A"]

    result = dedupe_by_group(ranked, groups)

    assert list(result) == [0, 1, 2]


def test_exploration_returns_the_requested_counts():
    ranked = np.arange(200)
    rng = np.random.default_rng(1234)

    result = split_exploration(ranked, n_total=10, n_explore=2, pool_size=100, rng=rng)

    assert len(result) == 10
    assert len(set(result)) == 10           # no duplicates
    assert list(result[:8]) == list(range(8))  # top 8 are the top of the ranking


def test_exploration_samples_from_within_the_pool():
    ranked = np.arange(200)
    rng = np.random.default_rng(1234)

    result = split_exploration(ranked, n_total=10, n_explore=2, pool_size=100, rng=rng)

    assert all(item < 100 for item in result[8:])


def test_exploration_degrades_gracefully_when_the_ranking_is_short():
    ranked = np.arange(5)
    rng = np.random.default_rng(1234)

    result = split_exploration(ranked, n_total=10, n_explore=2, pool_size=100, rng=rng)

    assert list(result) == [0, 1, 2, 3, 4]


def test_exploration_fills_the_batch_even_when_the_pool_is_small():
    """A pool smaller than the batch must not shrink the batch while the
    ranking still has items to give."""
    ranked = np.arange(200)
    rng = np.random.default_rng(1234)

    result = split_exploration(ranked, n_total=10, n_explore=2, pool_size=9, rng=rng)

    assert len(result) == 10
    assert len(set(result)) == 10
