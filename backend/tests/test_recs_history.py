from app.recs.history import summarise


def _rows(*events):
    """events: ("like", "a"), ("dislike", "b"), ("remove", "a"), ... oldest first."""
    return [{"product_id": pid, "type": kind} for kind, pid in events]


def _swipes(n, prefix="x"):
    return [("dislike", f"{prefix}{i}") for i in range(n)]


def test_a_like_counts_toward_taste_enters_the_wardrobe_and_is_hidden():
    h = summarise(_rows(("like", "a")))

    assert h.liked == ["a"] and h.wardrobe == ["a"]
    assert "a" in h.hidden and h.disliked == []


def test_a_dislike_counts_against_taste_and_is_hidden():
    h = summarise(_rows(("dislike", "a")))

    assert h.disliked == ["a"] and h.wardrobe == [] and "a" in h.hidden


def test_the_latest_vote_wins():
    changed_mind = summarise(_rows(("like", "a"), ("dislike", "a")))
    came_round = summarise(_rows(("dislike", "a"), ("like", "a")))

    assert changed_mind.liked == [] and changed_mind.disliked == ["a"]
    assert changed_mind.wardrobe == []
    assert came_round.liked == ["a"] and came_round.wardrobe == ["a"]


def test_liking_twice_counts_once():
    h = summarise(_rows(("like", "a"), ("like", "a")))

    assert h.liked == ["a"] and h.wardrobe == ["a"]


def test_removing_leaves_the_wardrobe_but_still_counts_as_a_like():
    h = summarise(_rows(("like", "a"), ("remove", "a")))

    assert h.wardrobe == []
    assert h.liked == ["a"]
    assert "a" in h.hidden  # cooling down


def test_a_removed_garment_returns_after_the_cool_down():
    just_short = summarise(_rows(("like", "a"), ("remove", "a"), *_swipes(19)), cooldown=20)
    long_enough = summarise(_rows(("like", "a"), ("remove", "a"), *_swipes(20)), cooldown=20)

    assert "a" in just_short.hidden
    assert "a" not in long_enough.hidden
    assert long_enough.liked == ["a"]  # still part of their taste


def test_disliking_a_returned_garment_hides_it_for_good():
    h = summarise(
        _rows(("like", "a"), ("remove", "a"), *_swipes(20), ("dislike", "a"), *_swipes(50, "y")),
        cooldown=20,
    )

    assert "a" in h.hidden and "a" in h.disliked and "a" not in h.liked


def test_liking_a_returned_garment_puts_it_back_in_the_wardrobe():
    h = summarise(_rows(("like", "a"), ("remove", "a"), *_swipes(20), ("like", "a")), cooldown=20)

    assert h.wardrobe == ["a"] and h.liked == ["a"]


def test_removing_something_not_in_the_wardrobe_changes_nothing():
    h = summarise(_rows(("dislike", "a"), ("remove", "a")))

    assert h.disliked == ["a"] and h.wardrobe == []


def test_wardrobe_lists_the_most_recently_liked_first():
    h = summarise(_rows(("like", "a"), ("like", "b"), ("like", "c")))

    assert h.wardrobe == ["c", "b", "a"]
    assert h.liked == ["a", "b", "c"]


def test_likes_dislikes_and_skips_count_as_cards_seen_and_other_types_are_ignored():
    h = summarise(_rows(("view", "a"), ("like", "b"), ("skip", "c"), ("dislike", "d")))

    assert h.swipes == 3
    assert "a" not in h.hidden


def test_the_default_cool_down_is_the_shared_constant(monkeypatch):
    from ml import constants

    monkeypatch.setattr(constants, "REMOVE_COOLDOWN_SWIPES", 1)

    h = summarise(_rows(("like", "a"), ("remove", "a"), ("dislike", "x")))

    assert "a" not in h.hidden


# --- "Not sure": the skip ---------------------------------------------------


def test_a_skip_hides_the_card_without_touching_taste_or_the_wardrobe():
    h = summarise(_rows(("skip", "a")))

    assert "a" in h.hidden
    assert h.liked == [] and h.disliked == [] and h.wardrobe == []
    assert h.swipes == 1


def test_a_skipped_card_comes_back_after_25_more_cards():
    still_waiting = summarise(_rows(("skip", "a"), *_swipes(24)))
    back = summarise(_rows(("skip", "a"), *_swipes(25)))

    assert "a" in still_waiting.hidden
    assert "a" not in back.hidden


def test_other_skips_count_towards_the_wait():
    """Someone who skips a lot still gets their skipped cards back."""
    h = summarise(_rows(("skip", "a"), *[("skip", f"s{i}") for i in range(25)]))

    assert "a" not in h.hidden


def test_a_later_like_or_dislike_overrides_a_skip():
    liked = summarise(_rows(("skip", "a"), ("like", "a"), *_swipes(30)))
    disliked = summarise(_rows(("skip", "a"), ("dislike", "a"), *_swipes(30)))

    assert liked.liked == ["a"] and liked.wardrobe == ["a"] and "a" in liked.hidden
    assert "a" in disliked.disliked and "a" in disliked.hidden


def test_a_skip_never_undoes_a_like_or_a_dislike():
    h = summarise(_rows(("like", "a"), ("dislike", "b"), ("skip", "a"), ("skip", "b"), *_swipes(30)))

    assert h.liked == ["a"] and h.wardrobe == ["a"] and "a" in h.hidden
    assert "b" in h.disliked and "b" in h.hidden


def test_the_skip_wait_is_the_shared_constant(monkeypatch):
    from ml import constants

    assert constants.SKIP_COOLDOWN_SWIPES == 25
    monkeypatch.setattr(constants, "SKIP_COOLDOWN_SWIPES", 1)

    h = summarise(_rows(("skip", "a"), ("dislike", "x")))

    assert "a" not in h.hidden
