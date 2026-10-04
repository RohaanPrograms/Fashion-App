import pandas as pd

from ml.matrix import build_interaction_matrix


def _transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["c1", "c1", "c2", "c3", "c3"],
            "article_id": ["a1", "a2", "a1", "a3", "a3"],
        }
    )


def test_matrix_shape_is_customers_by_articles():
    matrix, mapping = build_interaction_matrix(_transactions())

    assert matrix.shape == (3, 3)
    assert len(mapping.customer_ids) == 3
    assert len(mapping.article_ids) == 3


def test_repeat_purchases_accumulate():
    matrix, mapping = build_interaction_matrix(_transactions())

    row = mapping.customer_position("c3")
    col = mapping.article_position("a3")
    assert matrix[row, col] == 2


def test_position_round_trips_to_the_same_article():
    """The single most dangerous bug in this pipeline: if the mapping is wrong,
    every vector is attached to the wrong garment and nothing errors — the
    recommendations are simply nonsense."""
    _, mapping = build_interaction_matrix(_transactions())

    for article_id in mapping.article_ids:
        assert mapping.article_at(mapping.article_position(article_id)) == article_id


def test_mapping_is_deterministic_across_runs():
    first = build_interaction_matrix(_transactions())[1]
    second = build_interaction_matrix(_transactions())[1]

    assert first.article_ids == second.article_ids
    assert first.customer_ids == second.customer_ids


def test_unknown_article_raises_rather_than_returning_a_wrong_position():
    _, mapping = build_interaction_matrix(_transactions())

    try:
        mapping.article_position("nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError for an unknown article")


def test_row_order_does_not_change_the_mapping_or_matrix():
    """The same purchases read in a different order must number everything the
    same way, or vectors saved from one run attach to the wrong garments in the next."""
    matrix, mapping = build_interaction_matrix(_transactions())
    shuffled = _transactions().sample(frac=1, random_state=7).reset_index(drop=True)
    matrix_s, mapping_s = build_interaction_matrix(shuffled)

    assert mapping_s.customer_ids == mapping.customer_ids
    assert mapping_s.article_ids == mapping.article_ids
    assert (matrix_s != matrix).nnz == 0


def test_every_cell_matches_an_independent_count():
    transactions = pd.DataFrame(
        {
            "customer_id": ["c2", "c1", "c2", "c3", "c1", "c2", "c1"],
            "article_id": ["a3", "a1", "a3", "a2", "a1", "a1", "a3"],
        }
    )
    matrix, mapping = build_interaction_matrix(transactions)
    expected = transactions.value_counts().to_dict()

    for row, customer_id in enumerate(mapping.customer_ids):
        for col, article_id in enumerate(mapping.article_ids):
            assert matrix[row, col] == expected.get((customer_id, article_id), 0)


def test_category_dtype_ids_like_the_real_training_file():
    """train.parquet stores customer_id as a pandas category to save memory."""
    transactions = _transactions().astype({"customer_id": "category"})
    matrix, mapping = build_interaction_matrix(transactions)

    assert mapping.customer_ids == ["c1", "c2", "c3"]
    assert matrix[mapping.customer_position("c3"), mapping.article_position("a3")] == 2
