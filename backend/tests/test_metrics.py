import numpy as np
import pytest

from ml.metrics import (
    average_precision_at_k,
    map_at_k,
    mean_recall_at_k,
    recall_at_k,
)


def test_recall_is_the_share_of_relevant_items_found():
    # Two of the user's three real purchases appear in the top 4.
    assert recall_at_k([1, 2, 9, 8], {1, 2, 5}, k=4) == pytest.approx(2 / 3)


def test_recall_ignores_items_beyond_k():
    assert recall_at_k([9, 9, 9, 1], {1}, k=3) == 0.0


def test_recall_with_no_relevant_items_is_zero_not_a_crash():
    assert recall_at_k([1, 2], set(), k=2) == 0.0


def test_average_precision_rewards_ranking_hits_higher():
    early = average_precision_at_k([1, 9, 9, 9], {1}, k=4)
    late = average_precision_at_k([9, 9, 9, 1], {1}, k=4)

    assert early > late
    assert early == pytest.approx(1.0)
    assert late == pytest.approx(0.25)


def test_average_precision_hand_computed_two_hits():
    # Hits at positions 1 and 3. Precision 1/1 and 2/3; divided by min(k, |relevant|)=2.
    result = average_precision_at_k([1, 9, 2, 9], {1, 2}, k=4)

    assert result == pytest.approx((1.0 + 2 / 3) / 2)


def test_average_precision_is_zero_when_nothing_hits():
    assert average_precision_at_k([7, 8, 9], {1}, k=3) == 0.0


def test_map_averages_across_users():
    result = map_at_k([[1, 9], [9, 1]], [{1}, {1}], k=2)

    assert result == pytest.approx((1.0 + 0.5) / 2)


def test_mean_recall_averages_across_users():
    result = mean_recall_at_k([[1, 9], [9, 9]], [{1}, {1}], k=2)

    assert result == pytest.approx(0.5)


def test_map_with_no_users_is_zero():
    assert map_at_k([], [], k=12) == 0.0


def test_a_repeated_recommendation_counts_as_one_hit():
    """Otherwise recommending the same item twice scores 2.0, above the
    maximum of 1.0. Matches the official Kaggle MAP@12 scorer."""
    assert average_precision_at_k([1, 1], {1}, k=2) == pytest.approx(1.0)
    # The repeat also takes a slot: the second real hit is at position 3.
    assert average_precision_at_k([1, 1, 2], {1, 2}, k=3) == pytest.approx((1.0 + 2 / 3) / 2)


def test_mismatched_user_lists_raise_instead_of_silently_truncating():
    """Recommendations and purchases are paired user by user; if one list is
    shorter, every average after it would be computed over the wrong users."""
    with pytest.raises(ValueError):
        map_at_k([[1], [2]], [{1}], k=1)
    with pytest.raises(ValueError):
        mean_recall_at_k([[1], [2]], [{1}], k=1)


def test_accepts_numpy_arrays_from_the_ranking_functions():
    recommended = np.array([[1, 9], [9, 1]])

    assert map_at_k(recommended, [{1}, {1}], k=2) == pytest.approx(0.75)
    assert mean_recall_at_k(recommended, [{1}, {1}], k=2) == pytest.approx(1.0)
