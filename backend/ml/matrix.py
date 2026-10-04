"""Build the sparse customer x article matrix that ALS trains on.

WHY THE MAPPING MATTERS SO MUCH
-------------------------------
The matrix has no idea what a customer or an article is — it has row 0, row 1,
column 0, column 1. The mapping is the only thing connecting "column 37" back
to "article 0108775015". Lose it, or rebuild it in a different order, and
every vector silently attaches to the wrong garment. Nothing errors. The
recommendations just become nonsense. Hence the round-trip test.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix


@dataclass
class IndexMapping:
    """Two-way translation between IDs and matrix positions."""

    customer_ids: list[str]
    article_ids: list[str]
    _customer_pos: dict[str, int] = field(init=False, repr=False)
    _article_pos: dict[str, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._customer_pos = {cid: i for i, cid in enumerate(self.customer_ids)}
        self._article_pos = {aid: i for i, aid in enumerate(self.article_ids)}

    def customer_position(self, customer_id: str) -> int:
        return self._customer_pos[customer_id]

    def article_position(self, article_id: str) -> int:
        return self._article_pos[article_id]

    def article_at(self, position: int) -> str:
        return self.article_ids[position]


def build_interaction_matrix(
    transactions: pd.DataFrame,
) -> tuple[csr_matrix, IndexMapping]:
    """Build a customers x articles matrix of purchase counts.

    IDs are sorted before being assigned positions, so the same transactions
    always produce the same mapping regardless of row order.
    """
    customer_ids = sorted(transactions["customer_id"].unique())
    article_ids = sorted(transactions["article_id"].unique())
    mapping = IndexMapping(customer_ids=customer_ids, article_ids=article_ids)

    # Explicit int64: mapping a category column can return a category column,
    # which scipy would not accept as positions.
    rows = transactions["customer_id"].map(mapping.customer_position).to_numpy(np.int64)
    cols = transactions["article_id"].map(mapping.article_position).to_numpy(np.int64)
    values = np.ones(len(transactions), dtype=np.float32)

    matrix = csr_matrix(
        (values, (rows, cols)),
        shape=(len(customer_ids), len(article_ids)),
        dtype=np.float32,
    )
    # Duplicate (row, col) entries are summed by csr_matrix, which is exactly
    # what we want: buying the same item twice is a stronger signal.
    matrix.sum_duplicates()
    return matrix, mapping
