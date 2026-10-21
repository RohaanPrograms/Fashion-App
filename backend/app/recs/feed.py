"""Choose the next batch of cards for one user. Pure: no database, no network.

Every ranking step comes from ml.ranking — the functions the offline
evaluation scored — so the reported numbers describe this feed.

  fewer than COLD_START_LIKES likes -> best-sellers (popularity)
  otherwise -> style vector (likes minus discounted dislikes) -> cosine rank
  then, either way: drop hidden garments -> one colour per design ->
  top picks plus a few explorations from further down the ranking.

Each card carries its reason ("why am I seeing this?"): the similarity to the
user's style and the liked garment it is closest to. The numbers exist anyway,
and showing them makes the model visible.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from app.recs.catalog import Catalog, Product
from app.recs.history import History
from ml import constants
from ml.ranking import (
    build_style_vector,
    dedupe_by_group,
    exclude_positions,
    rank_by_similarity,
    split_exploration,
)

POPULAR, SIMILAR, EXPLORE = "popular", "similar", "explore"


@dataclass(frozen=True)
class Reason:
    kind: str  # POPULAR, SIMILAR or EXPLORE
    similarity: float | None  # cosine similarity to the user's style
    because_of: Product | None  # the liked garment this card is closest to


@dataclass(frozen=True)
class FeedItem:
    product: Product
    reason: Reason


@dataclass(frozen=True)
class Feed:
    items: list[FeedItem]
    personalised: bool
    likes: int
    likes_needed: int


def explore_count(limit: int) -> int:
    """EXPLORE_COUNT per FEED_BATCH_SIZE cards, scaled to the batch asked for."""
    return round(limit * constants.EXPLORE_COUNT / constants.FEED_BATCH_SIZE)


def _positions(catalog: Catalog, product_ids: Iterable[str]) -> list[int]:
    """Catalogue rows for these ids; ids not in the catalogue are skipped."""
    found = (catalog.position(p) for p in product_ids)
    return [p for p in found if p is not None]


def build_feed(
    catalog: Catalog, history: History, limit: int, rng: np.random.Generator
) -> Feed:
    liked = _positions(catalog, history.liked)
    disliked = _positions(catalog, history.disliked)
    hidden = set(_positions(catalog, history.hidden))
    personalised = len(liked) >= constants.COLD_START_LIKES

    style = None
    if personalised:
        style = build_style_vector(
            catalog.vectors[liked], catalog.vectors[disliked] if disliked else None
        )
        ranked = rank_by_similarity(style, catalog.vectors)
        kind = SIMILAR
    else:
        ranked = np.argsort(-catalog.popularity, kind="stable")
        kind = POPULAR

    ranked = exclude_positions(ranked, hidden)
    ranked = dedupe_by_group(ranked, catalog.groups)
    n_explore = explore_count(limit)
    chosen = split_exploration(
        ranked, n_total=limit, n_explore=n_explore, pool_size=constants.EXPLORE_POOL, rng=rng
    )
    # split_exploration returns everything, un-split, when there is no more
    # than a batch left; then every card is a top pick.
    n_top = limit - n_explore if len(ranked) > limit else len(chosen)

    items = [
        FeedItem(
            product=catalog.products[position],
            reason=_reason(catalog, int(position), kind if i < n_top else EXPLORE, style, liked),
        )
        for i, position in enumerate(chosen)
    ]
    return Feed(
        items=items,
        personalised=personalised,
        likes=len(liked),
        likes_needed=constants.COLD_START_LIKES,
    )


def _reason(
    catalog: Catalog, position: int, kind: str, style: np.ndarray | None, liked: list[int]
) -> Reason:
    if style is None:
        return Reason(kind=kind, similarity=None, because_of=None)
    unit_style = style / max(float(np.linalg.norm(style)), 1e-12)
    similarity = float(catalog.unit[position] @ unit_style)
    nearest = liked[int(np.argmax(catalog.unit[liked] @ catalog.unit[position]))]
    return Reason(kind=kind, similarity=round(similarity, 4), because_of=catalog.products[nearest])
