"""ALS training, plus the pure helpers that turn its output into database rows.

WHY ALS FITS THIS DATA
----------------------
With star ratings, a blank cell means "unrated". With purchases, a blank
almost always means "never saw it" — nobody browses 105,000 garments — not
"rejected". Implicit-feedback ALS handles that by splitting a *preference*
(1 if bought, 0 otherwise) from a *confidence* in that preference, scaled by
`alpha`. Blanks become zeros held weakly rather than rejections.

Purchase counts are used raw, so one customer buying an item 80 times gives
that cell a confidence of 1 + 40 x 80. Whether that lets a few bulk buyers
skew the vectors is checked in the cold-start evaluation before anything is
done about it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
from implicit.als import AlternatingLeastSquares
from scipy.sparse import csr_matrix
from threadpoolctl import threadpool_limits

from ml.constants import RANDOM_SEED

MODEL_FAMILY = "als"
MODEL_REVISION = "v1"


def model_version(factors: int) -> str:
    """Identifier stored on every vector row.

    Vectors from different runs are not comparable; mixing them returns
    nonsense rather than an error, so every row records where it came from.
    """
    return f"{MODEL_FAMILY}-{factors}f-{MODEL_REVISION}"


def train_als(
    matrix: csr_matrix,
    factors: int,
    regularization: float = 0.05,
    iterations: int = 15,
    alpha: float = 40.0,
    seed: int = RANDOM_SEED,
) -> np.ndarray:
    """Train ALS and return the item factors.

    Args:
        matrix: customers x articles purchase counts.
        factors: how many hidden traits to learn.
        regularization: penalty that stops values growing extreme to chase noise.
        iterations: how many times to alternate between solving for users and items.
        alpha: how strongly a purchase counts as confident evidence.
        seed: fixed for reproducibility.

    Returns:
        Item factors, shape (n_articles, factors). The user factors are
        discarded — the app has no H&M customers, so it never uses them.
    """
    # implicit already trains in parallel; letting the maths library underneath
    # (OpenBLAS) start its own threads as well makes them fight over the CPU,
    # which implicit warns can be ~10x slower. One BLAS thread, as it advises.
    with threadpool_limits(1, "blas"):
        model = AlternatingLeastSquares(
            factors=factors,
            regularization=regularization,
            iterations=iterations,
            alpha=alpha,
            random_state=seed,
            calculate_training_loss=False,
        )
        model.fit(matrix, show_progress=False)
    return np.asarray(model.item_factors)


def build_vector_rows(
    vectors: np.ndarray,
    article_ids: Sequence[str],
    product_id_by_article: dict[str, str],
    version: str,
) -> tuple[list[dict], int]:
    """Pair each vector with its products.id, ready for product_vectors.

    vectors[i] belongs to article_ids[i] (the IndexMapping order); the dict
    translates H&M's article id into our own product UUID. Articles with no
    product row are skipped and counted, so a mismatch shows in the output
    instead of passing silently.

    Returns:
        (rows, skipped)
    """
    rows = []
    skipped = 0
    for position, article_id in enumerate(article_ids):
        product_id = product_id_by_article.get(article_id)
        if product_id is None:
            skipped += 1
            continue
        rows.append(
            {
                "product_id": product_id,
                # Plain floats: numpy's float32 cannot be serialised to JSON.
                "vector": [float(value) for value in vectors[position]],
                "model_version": version,
            }
        )
    return rows, skipped


def fetch_all_pages(
    fetch_page: Callable[[int, int], list], page_size: int = 1000
) -> list:
    """Collect every row from a paged query.

    Supabase returns at most 1,000 rows per request, so a single select over
    5,000 products quietly returns only the first 1,000. `fetch_page(start,
    end)` must return rows start..end inclusive, as Supabase's range() does.
    A page shorter than page_size means there is nothing left.
    """
    rows: list = []
    start = 0
    while True:
        page = fetch_page(start, start + page_size - 1)
        rows.extend(page)
        if len(page) < page_size:
            return rows
        start += page_size
