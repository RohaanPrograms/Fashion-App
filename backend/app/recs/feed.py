"""Choose the next batch of cards for one user. Pure: no database, no network.

Every ranking step comes from ml.ranking — the functions the offline
evaluation scored — so the reported numbers describe this feed.

  fewer than COLD_START_LIKES likes -> best-sellers (popularity)
  otherwise -> style vector (likes minus discounted dislikes) -> cosine rank
  then, either way: drop hidden garments AND their other colours -> one
  colour per design -> top picks plus a few explorations from further down
  the ranking. With a filter, that happens per pick and the picks take turns.

Other colours are hidden because H&M sells one design as several articles.
Without it, a swiped pair of jeans comes back in three more colours, one
batch later. (The offline evaluation didn't do this: real shoppers do
sometimes buy a second colour. In a swipe feed, repeats are worse.)

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


def _with_other_colours(catalog: Catalog, hidden: set[int]) -> set[int]:
    """Add every row that shares a design (product_code) with a hidden row."""
    designs = {catalog.groups[p] for p in hidden} - {None}
    return hidden | {i for i, group in enumerate(catalog.groups) if group in designs}


def _even_split(total: int, parts: int) -> list[int]:
    """10 cards over 3 picks -> [4, 3, 3]."""
    base, extra = divmod(total, parts)
    return [base + (i < extra) for i in range(parts)]


def _choose(ranked: np.ndarray, n: int, rng: np.random.Generator) -> list[tuple[int, bool]]:
    """The top of `ranked` plus a few explorations: (position, explored?) pairs."""
    if n <= 0:
        return []
    n_explore = explore_count(n)
    chosen = split_exploration(
        ranked, n_total=n, n_explore=n_explore, pool_size=constants.EXPLORE_POOL, rng=rng
    )
    # split_exploration returns everything, un-split, when there is no more
    # than a batch left; then every card is a top pick.
    n_top = n - n_explore if len(ranked) > n else len(chosen)
    return [(int(p), i >= n_top) for i, p in enumerate(chosen)]


def _take_turns(
    lanes: list[list[tuple[int, bool]]], limit: int, groups: list[str | None]
) -> list[tuple[int, bool]]:
    """One card from each lane in turn until `limit`, skipping any card (or
    other colour of a design) already taken: two picks can overlap."""
    queues = [list(lane) for lane in lanes]
    taken: list[tuple[int, bool]] = []
    seen_positions: set[int] = set()
    seen_designs: set[str] = set()
    while len(taken) < limit and any(queues):
        for queue in queues:
            while queue and len(taken) < limit:
                position, explored = queue.pop(0)
                design = groups[position]
                if position in seen_positions or (design is not None and design in seen_designs):
                    continue
                seen_positions.add(position)
                if design is not None:
                    seen_designs.add(design)
                taken.append((position, explored))
                break
    return taken


def build_feed(
    catalog: Catalog,
    history: History,
    limit: int,
    rng: np.random.Generator,
    keeps: list[np.ndarray] | None = None,
) -> Feed:
    """`keeps`: one mask per filter pick (Catalog.matching); None or [] = no filter.

    With several picks the feed TAKES TURNS: each pick gets its own lane,
    ranked by the same taste, and the batch alternates between them. A pick
    that runs dry hands its share to the others.

    The filter narrows what is shown, never what is learned: the style vector
    is built from every like, whichever filter it was made under.
    """
    liked = _positions(catalog, history.liked)
    disliked = _positions(catalog, history.disliked)
    hidden = _with_other_colours(catalog, set(_positions(catalog, history.hidden)))
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

    if not keeps:
        chosen = _choose(ranked, limit, rng)
    else:
        lanes_ranked = [ranked[keep[ranked]] for keep in keeps]
        lanes = [
            _choose(lane, share, rng)
            for lane, share in zip(lanes_ranked, _even_split(limit, len(keeps)))
        ]
        # Then the rest of each lane, best first, to fill any share left
        # unused by a lane that ran dry.
        spares = [
            [(int(p), False) for p in lane if int(p) not in {q for q, _ in picked}]
            for lane, picked in zip(lanes_ranked, lanes)
        ]
        chosen = _take_turns(lanes, limit, catalog.groups)
        if len(chosen) < limit:
            already = {p for p, _ in chosen}
            spares = [[c for c in spare if c[0] not in already] for spare in spares]
            chosen += _take_turns(spares, limit - len(chosen), catalog.groups)

    items = [
        FeedItem(
            product=catalog.products[position],
            reason=_reason(catalog, position, EXPLORE if explored else kind, style, liked),
        )
        for position, explored in chosen
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
