import numpy as np
import pytest

from app.recs.feed import EXPLORE, POPULAR, SIMILAR, build_feed, explore_count
from app.recs.history import summarise


def _history(likes=(), dislikes=()):
    rows = [{"product_id": p, "type": "like"} for p in likes]
    rows += [{"product_id": p, "type": "dislike"} for p in dislikes]
    return summarise(rows)


def _names(feed, small_catalog_ids):
    by_id = {v: k for k, v in small_catalog_ids.items()}
    return [by_id[item.product.id] for item in feed.items]


def _cos(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_cold_start_shows_best_sellers_one_colour_per_design(small_catalog, ids):
    feed = build_feed(small_catalog, _history(), limit=2, rng=np.random.default_rng(0))

    # black_tee 900, white_tee 800 (same design T1, dropped), jeans 700
    assert _names(feed, ids) == ["black_tee", "jeans"]
    assert not feed.personalised and feed.likes == 0 and feed.likes_needed == 3
    assert all(item.reason.kind == POPULAR for item in feed.items)
    assert all(item.reason.because_of is None for item in feed.items)


def test_cold_start_never_shows_what_was_already_swiped_in_any_colour(small_catalog, ids):
    feed = build_feed(
        small_catalog, _history(likes=[ids["black_tee"]]), limit=2, rng=np.random.default_rng(0)
    )

    # black_tee is hidden, and so is white_tee: the same design in another colour
    assert _names(feed, ids) == ["jeans", "dress"]


def test_personalises_from_the_shared_constant(small_catalog, ids, monkeypatch):
    from ml import constants

    two_likes = _history(likes=[ids["dress"], ids["heels"]])
    assert not build_feed(small_catalog, two_likes, 2, np.random.default_rng(0)).personalised

    monkeypatch.setattr(constants, "COLD_START_LIKES", 2)
    assert build_feed(small_catalog, two_likes, 2, np.random.default_rng(0)).personalised


def test_evaluation_and_feed_use_the_same_cold_start_constant():
    """If these drifted apart, the README's headline number would describe a
    different system from the one that ships."""
    import ml.evaluate
    from ml import constants

    assert ml.evaluate.COLD_START_LIKES == constants.COLD_START_LIKES


def test_personalised_feed_ranks_by_similarity_and_explains_itself(small_catalog, ids):
    liked = ["dress", "heels", "belt"]
    feed = build_feed(
        small_catalog,
        _history(likes=[ids[n] for n in liked]),
        limit=2,
        rng=np.random.default_rng(0),
    )

    # style = mean of [0,1], [0.1,0.95], [0.5,0.5] = [0.2, 0.8167]
    # cosine: jeans 0.564 > striped_tee 0.443 > sneakers 0.373 > white_tee 0.287
    # (> black_tee 0.238, same design as white_tee, so deduped away)
    assert feed.personalised and feed.likes == 3
    assert _names(feed, ids) == ["jeans", "striped_tee"]
    first = feed.items[0].reason
    assert first.kind == SIMILAR
    style = np.mean([[0.0, 1.0], [0.1, 0.95], [0.5, 0.5]], axis=0)
    assert first.similarity == pytest.approx(_cos(style, [0.8, 0.3]), abs=1e-3)
    # of the liked garments, the belt points closest to the jeans
    assert first.because_of.id == ids["belt"]


def test_explore_count_scales_with_the_batch():
    assert explore_count(10) == 2
    assert explore_count(1) == 0
    assert explore_count(5) == 1
    assert explore_count(50) == 10


def test_a_full_batch_is_eight_top_picks_and_two_explorations(make_catalog):
    catalog = make_catalog(60)
    likes = [p.id for p in catalog.products[:3]]

    feed = build_feed(catalog, _history(likes=likes), limit=10, rng=np.random.default_rng(1))

    kinds = [item.reason.kind for item in feed.items]
    assert kinds == [SIMILAR] * 8 + [EXPLORE] * 2
    assert len({item.product.id for item in feed.items}) == 10


def test_the_end_of_the_catalogue_returns_what_is_left(small_catalog, ids):
    everything_but_belt = [ids[n] for n in ids if n != "belt"]

    feed = build_feed(
        small_catalog, _history(dislikes=everything_but_belt), limit=10, rng=np.random.default_rng(0)
    )

    assert _names(feed, ids) == ["belt"]


def test_unknown_products_in_the_history_are_ignored(small_catalog):
    feed = build_feed(
        small_catalog,
        _history(likes=["not-in-catalogue-1", "not-in-catalogue-2", "not-in-catalogue-3"]),
        limit=3,
        rng=np.random.default_rng(0),
    )

    assert not feed.personalised and feed.likes == 0
    assert len(feed.items) == 3


@pytest.mark.parametrize("seed", range(40))
def test_hidden_garments_never_appear_and_designs_never_repeat(make_catalog, seed):
    """Random histories, the same promises every time."""
    catalog = make_catalog(40, seed=seed)
    rng = np.random.default_rng(seed)
    product_ids = [p.id for p in catalog.products]
    rows = [
        {"product_id": product_ids[i], "type": kind}
        for i, kind in zip(
            rng.integers(0, 40, size=25), rng.choice(["like", "dislike", "remove"], size=25)
        )
    ]
    history = summarise(rows)

    feed = build_feed(catalog, history, limit=10, rng=rng)

    shown = [item.product.id for item in feed.items]
    assert not set(shown) & history.hidden
    assert len(shown) == len(set(shown)) <= 10
    codes = [item.product.product_code for item in feed.items]
    assert len(codes) == len(set(codes))


def test_a_category_filter_keeps_only_that_category(small_catalog, ids):
    from app.recs.filters import parse_pick

    keep = small_catalog.matching(parse_pick("shoes"))
    feed = build_feed(small_catalog, _history(), limit=10, rng=np.random.default_rng(0), keeps=[keep])

    assert _names(feed, ids) == ["heels", "sneakers"]  # best-sellers among shoes


def test_a_filtered_feed_is_still_ranked_by_taste(small_catalog, ids):
    from app.recs.filters import parse_pick

    keep = small_catalog.matching(parse_pick("tops"))
    history = _history(likes=[ids["dress"], ids["heels"], ids["belt"]])
    feed = build_feed(small_catalog, history, limit=2, rng=np.random.default_rng(0), keeps=[keep])

    # Best-sellers would put black_tee first; this user's style ranks
    # striped_tee (0.443) above white_tee (0.287) above black_tee (0.238).
    assert feed.personalised
    assert _names(feed, ids) == ["striped_tee", "white_tee"]


def test_a_type_filter_narrows_further(small_catalog, ids):
    from app.recs.filters import parse_pick

    keep = small_catalog.matching(parse_pick("bottoms:trousers"))
    feed = build_feed(small_catalog, _history(), limit=10, rng=np.random.default_rng(0), keeps=[keep])

    assert _names(feed, ids) == ["jeans"]


def test_disliking_one_colour_hides_the_others(small_catalog, ids):
    feed = build_feed(
        small_catalog, _history(dislikes=[ids["white_tee"]]), limit=10, rng=np.random.default_rng(0)
    )

    assert "black_tee" not in _names(feed, ids)


def _keeps(catalog, *picks):
    from app.recs.filters import parse_pick

    return [catalog.matching(parse_pick(p)) for p in picks]


def test_several_picks_take_turns(small_catalog, ids):
    keeps = _keeps(small_catalog, "tops:t-shirts", "shoes")
    feed = build_feed(small_catalog, _history(), limit=4, rng=np.random.default_rng(0), keeps=keeps)

    # Best-sellers within each pick, alternating: tee, shoe, tee, shoe
    assert _names(feed, ids) == ["black_tee", "heels", "striped_tee", "sneakers"]


def test_a_pick_that_runs_dry_hands_its_share_to_the_others(small_catalog, ids):
    keeps = _keeps(small_catalog, "bottoms:trousers", "tops")
    feed = build_feed(small_catalog, _history(), limit=3, rng=np.random.default_rng(0), keeps=keeps)

    # Trousers has only the jeans; tops fills the rest of the batch.
    assert _names(feed, ids) == ["jeans", "black_tee", "striped_tee"]


def test_overlapping_picks_never_show_a_card_twice(small_catalog, ids):
    keeps = _keeps(small_catalog, "tops", "tops:t-shirts")
    feed = build_feed(small_catalog, _history(), limit=4, rng=np.random.default_rng(0), keeps=keeps)

    assert _names(feed, ids) == ["black_tee", "striped_tee"]
