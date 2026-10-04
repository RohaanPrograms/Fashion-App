import numpy as np
import pandas as pd

from ml.matrix import build_interaction_matrix
from ml.train import build_vector_rows, fetch_all_pages, model_version, train_als


def _clustered_transactions() -> pd.DataFrame:
    """Two clean buying groups: customers who buy a1/a2, and ones who buy a3/a4.

    With this structure a working ALS must place a1 near a2 and a3 near a4.
    """
    rows = []
    for i in range(30):
        rows += [
            {"customer_id": f"casual{i}", "article_id": "a1"},
            {"customer_id": f"casual{i}", "article_id": "a2"},
            {"customer_id": f"dressy{i}", "article_id": "a3"},
            {"customer_id": f"dressy{i}", "article_id": "a4"},
        ]
    return pd.DataFrame(rows)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_returns_one_vector_per_article_with_the_requested_width():
    matrix, mapping = build_interaction_matrix(_clustered_transactions())

    factors = train_als(matrix, factors=8, iterations=5)

    assert factors.shape == (len(mapping.article_ids), 8)


def test_co_purchased_items_end_up_closer_than_unrelated_ones():
    """The core claim of the whole project, on data small enough to verify."""
    matrix, mapping = build_interaction_matrix(_clustered_transactions())

    vectors = train_als(matrix, factors=8, iterations=20)

    a1 = vectors[mapping.article_position("a1")]
    a2 = vectors[mapping.article_position("a2")]
    a3 = vectors[mapping.article_position("a3")]

    assert _cosine(a1, a2) > _cosine(a1, a3)


def test_same_seed_gives_identical_vectors():
    matrix, _ = build_interaction_matrix(_clustered_transactions())

    first = train_als(matrix, factors=8, iterations=5, seed=99)
    second = train_als(matrix, factors=8, iterations=5, seed=99)

    assert np.allclose(first, second)


def test_model_version_encodes_the_factor_count():
    assert model_version(64) == "als-64f-v1"


def test_vector_rows_attach_each_vector_to_its_own_product():
    vectors = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], dtype=np.float32)
    article_ids = ["a1", "a2", "a3"]
    # Deliberately not in article order, so a position mix-up would show.
    product_id_by_article = {"a3": "uuid-3", "a1": "uuid-1", "a2": "uuid-2"}

    rows, skipped = build_vector_rows(
        vectors, article_ids, product_id_by_article, "als-2f-v1"
    )

    assert skipped == 0
    assert rows == [
        {"product_id": "uuid-1", "vector": [1.0, 2.0], "model_version": "als-2f-v1"},
        {"product_id": "uuid-2", "vector": [3.0, 4.0], "model_version": "als-2f-v1"},
        {"product_id": "uuid-3", "vector": [5.0, 6.0], "model_version": "als-2f-v1"},
    ]


def test_vector_rows_skip_and_count_articles_with_no_product():
    vectors = np.array([[1.0], [2.0]], dtype=np.float32)

    rows, skipped = build_vector_rows(vectors, ["a1", "a2"], {"a2": "uuid-2"}, "v")

    assert skipped == 1
    assert [row["product_id"] for row in rows] == ["uuid-2"]


def test_vector_rows_hold_plain_floats_for_json():
    """numpy float32 cannot be serialised to JSON; the upload would fail."""
    vectors = np.array([[0.5]], dtype=np.float32)

    rows, _ = build_vector_rows(vectors, ["a1"], {"a1": "uuid-1"}, "v")

    assert type(rows[0]["vector"][0]) is float


def test_fetch_all_pages_collects_past_the_first_page():
    """Supabase returns at most 1,000 rows per request; one request is not enough."""
    data = list(range(2345))
    calls = []

    def fetch_page(start: int, end: int) -> list[int]:
        calls.append((start, end))
        return data[start : end + 1]  # end is inclusive, as in Supabase's range()

    result = fetch_all_pages(fetch_page, page_size=1000)

    assert result == data
    assert calls == [(0, 999), (1000, 1999), (2000, 2999)]


def test_fetch_all_pages_stops_after_an_exactly_full_last_page():
    data = list(range(2000))

    result = fetch_all_pages(lambda s, e: data[s : e + 1], page_size=1000)

    assert result == data
