from ml import constants


def test_catalog_quotas_sum_to_catalog_size():
    """If quotas drift out of sync with the target, Stage 1 silently produces
    the wrong catalog size and every downstream number shifts."""
    assert sum(constants.CATEGORY_QUOTAS.values()) == constants.CATALOG_SIZE


def test_cold_start_likes_is_positive():
    assert constants.COLD_START_LIKES >= 1


def test_explore_count_fits_in_batch():
    assert constants.EXPLORE_COUNT < constants.FEED_BATCH_SIZE
