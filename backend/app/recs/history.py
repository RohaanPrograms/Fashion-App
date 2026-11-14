"""Turn a user's interaction log into what the feed and the wardrobe need.

THE RULE: the most recent action on a garment decides its state.

- like    -> counts toward taste; in the wardrobe; hidden from the feed.
- dislike -> counts against taste; out of the wardrobe; hidden for good.
- remove  -> out of the wardrobe, but STILL counts as a like: the user liked
             that kind of garment. Hidden only until REMOVE_COOLDOWN_SWIPES
             more swipes have happened, then allowed back into the feed.
             Without the cool-down it would reappear at once, because a liked
             garment is the closest thing there is to the user's own taste.
- skip    -> "Not sure". Says nothing about taste and never undoes a like or
             a dislike. Hides the card until SKIP_COOLDOWN_SWIPES more cards
             have been seen; a later like or dislike replaces it.

Likes, dislikes and skips are all "swipes" (cards seen), so the cool-downs
run even for someone who skips a lot. Other recorded types (view, wishlist,
cart) are not produced by the app and are ignored here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ml import constants

LIKE, DISLIKE, REMOVE, SKIP = "like", "dislike", "remove", "skip"


@dataclass(frozen=True)
class History:
    liked: list[str]  # count toward taste, oldest like first
    disliked: list[str]
    wardrobe: list[str]  # most recently liked first
    hidden: frozenset[str]  # must not appear in the feed right now
    swipes: int


def summarise(
    rows: Iterable[dict], cooldown: int | None = None, skip_cooldown: int | None = None
) -> History:
    """`rows` are {"product_id", "type"} dicts, oldest first."""
    # Read at call time, through the module, so there is one source of truth.
    if cooldown is None:
        cooldown = constants.REMOVE_COOLDOWN_SWIPES
    if skip_cooldown is None:
        skip_cooldown = constants.SKIP_COOLDOWN_SWIPES

    vote: dict[str, str] = {}  # product -> LIKE or DISLIKE
    liked_at: dict[str, int] = {}  # product -> swipe number of its latest like
    in_wardrobe: set[str] = set()
    removed_at: dict[str, int] = {}  # product -> swipe count when it was removed
    skipped_at: dict[str, int] = {}  # product -> swipe count just after its latest skip
    swipes = 0

    for row in rows:
        product_id, kind = row["product_id"], row["type"]
        if kind == LIKE:
            swipes += 1
            vote[product_id] = LIKE
            liked_at[product_id] = swipes
            in_wardrobe.add(product_id)
            removed_at.pop(product_id, None)
            skipped_at.pop(product_id, None)
        elif kind == DISLIKE:
            swipes += 1
            vote[product_id] = DISLIKE
            in_wardrobe.discard(product_id)
            removed_at.pop(product_id, None)
            skipped_at.pop(product_id, None)
        elif kind == SKIP:
            swipes += 1
            # A vote already made stands; the skip only matters for cards
            # without one (the feed never shows voted cards anyway).
            if product_id not in vote:
                skipped_at[product_id] = swipes
        elif kind == REMOVE and product_id in in_wardrobe:
            in_wardrobe.discard(product_id)
            removed_at[product_id] = swipes

    cooling = {p for p, at in removed_at.items() if swipes - at < cooldown}
    cooling |= {p for p, at in skipped_at.items() if swipes - at < skip_cooldown}
    disliked = [p for p, v in vote.items() if v == DISLIKE]
    return History(
        liked=sorted((p for p, v in vote.items() if v == LIKE), key=liked_at.__getitem__),
        disliked=disliked,
        wardrobe=sorted(in_wardrobe, key=liked_at.__getitem__, reverse=True),
        hidden=frozenset(disliked) | frozenset(in_wardrobe) | frozenset(cooling),
        swipes=swipes,
    )
