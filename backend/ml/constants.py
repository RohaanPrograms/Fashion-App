"""Tunables shared by the offline pipeline and (in Phase 2) the live API.

The evaluation and the feed endpoint import these rather than keeping their own
copies: if the two disagreed, the README's headline metric would describe a
system different from the one that ships.
"""

# Likes needed before the feed switches from popularity to personalised.
# Imported by BOTH ml/evaluate.py and (Phase 2) the feed endpoint.
COLD_START_LIKES = 3

# Weight on disliked items when building a style vector. Unvalidated
# heuristic: the dataset contains no dislikes.
DISLIKE_WEIGHT = 0.3

# Feed batching and exploration.
FEED_BATCH_SIZE = 10
EXPLORE_COUNT = 2      # of each batch, how many are sampled rather than top-ranked
EXPLORE_POOL = 100     # sampled from the top N of the ranking

# Every source of randomness in the project uses this, so results reproduce.
RANDOM_SEED = 1234

# Catalog subset. Quotas must sum to CATALOG_SIZE —
# tests/test_constants.py enforces it. Keys must match product_group_name in
# articles.csv exactly; a mismatched key silently selects zero articles.
CATALOG_SIZE = 5000
CATEGORY_QUOTAS = {
    "Garment Upper body": 1600,
    "Garment Lower body": 1300,
    "Garment Full body": 900,
    "Shoes": 700,
    "Accessories": 500,
}

# Training window and evaluation.
TRAINING_WINDOW_MONTHS = 6
HOLDOUT_DAYS = 14
EVAL_K = 12   # matches the H&M Kaggle competition's MAP@12
