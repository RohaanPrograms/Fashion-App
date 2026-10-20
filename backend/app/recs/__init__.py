"""Recommendations: the pure, in-memory side of the feed.

Nothing in this package talks to the network except load_catalog(), which is
given a client. Ranking logic itself lives in ml.ranking, shared with the
offline evaluation.
"""
