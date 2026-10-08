"""Run the cold-start evaluation and write the metrics file the README quotes.

    cd backend
    python -m scripts.run_evaluation --train ../data/train.parquet \
        --holdout ../data/holdout.parquet --subset ../data/subset.csv \
        --out ../docs/metrics.json

Trains ALS at each factor count, with raw and with log-scaled purchase counts,
and scores every model and both baselines on the same simulated visitors.
Takes around ten minutes. Logic lives in ml/evaluate.py.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from ml.constants import COLD_START_LIKES, EVAL_K, RANDOM_SEED
from ml.evaluate import (
    BOOTSTRAP_RESAMPLES,
    CONFIDENCE,
    build_eval_cases,
    compare,
    evaluate_model,
    evaluate_popularity,
    evaluate_random,
)
from ml.matrix import build_interaction_matrix
from ml.train import COUNT_SCALINGS, model_version, train_als

FACTOR_SETTINGS = [32, 64, 128, 256]


def _interval(values: list[float]) -> str:
    return f"[{values[0]:.4f}, {values[1]:.4f}]"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--holdout", required=True, type=Path)
    parser.add_argument("--subset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    train = pd.read_parquet(args.train)
    holdout = pd.read_parquet(args.holdout)
    subset = pd.read_csv(args.subset, dtype={"article_id": str, "product_code": str})

    matrix, mapping = build_interaction_matrix(train)

    # Design (product_code) of each matrix column, for the one-colourway-per-
    # design step. A gap means the subset and training data don't match.
    groups = (
        subset.set_index("article_id")["product_code"]
        .reindex(mapping.article_ids)
        .tolist()
    )
    missing = sum(pd.isna(group) for group in groups)
    if missing:
        raise SystemExit(
            f"{missing} trained articles have no product_code in {args.subset} — "
            "was the training set built from a different subset?"
        )

    cases = build_eval_cases(holdout, mapping)
    print(f"{len(cases):,} simulated visitors, seeded with {COLD_START_LIKES} likes")
    if not cases:
        raise SystemExit("No eligible holdout customers — widen the holdout window.")

    popularity = (
        train["article_id"]
        .value_counts()
        .reindex(mapping.article_ids)
        .fillna(0)
        .to_numpy(dtype=float)
    )
    popularity_scores = evaluate_popularity(cases, popularity, EVAL_K, groups)
    random_scores = evaluate_random(
        cases,
        n_items=len(mapping.article_ids),
        k=EVAL_K,
        groups=groups,
        rng=np.random.default_rng(RANDOM_SEED),
    )

    results = {
        "generated_on": date.today().isoformat(),
        "k": EVAL_K,
        "cold_start_likes": COLD_START_LIKES,
        "n_articles": len(mapping.article_ids),
        "n_designs": len(set(groups)),
        "n_train_rows": int(len(train)),
        "n_visitors": len(cases),
        "method": {
            "served_as": "seeds excluded, one colourway per product_code",
            "exploration_slots": "excluded",
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "interval": f"{CONFIDENCE:.0%}",
        },
        "baselines": {
            "popularity": popularity_scores.summary(),
            "random": random_scores.summary(),
        },
        "models": {},
    }

    for scaling in COUNT_SCALINGS:
        for factors in FACTOR_SETTINGS:
            version = model_version(factors, scaling)
            started = time.perf_counter()
            vectors = train_als(matrix, factors=factors, scaling=scaling)
            trained_in = time.perf_counter() - started
            scores = evaluate_model(cases, vectors, EVAL_K, groups)

            entry = scores.summary()
            entry["vs_popularity"] = compare(scores, popularity_scores)
            entry["train_seconds"] = round(trained_in, 1)
            results["models"][version] = entry
            print(
                f"{version}: recall@{EVAL_K} {entry['recall_at_k']:.4f}  "
                f"(trained in {trained_in:.0f}s)"
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    print(
        f"\n{'':<16}{'recall@12':>10} {'95% interval':>18}  {'MAP@12':>8} {'95% interval':>18}"
        f"  {'new designs':>11} {'95% interval':>18}"
    )
    rows = [
        ("popularity", results["baselines"]["popularity"]),
        ("random", results["baselines"]["random"]),
        *results["models"].items(),
    ]
    for name, entry in rows:
        print(
            f"{name:<16}{entry['recall_at_k']:>10.4f} {_interval(entry['recall_ci95']):>18}  "
            f"{entry['map_at_k']:>8.4f} {_interval(entry['map_ci95']):>18}  "
            f"{entry['new_design_recall_at_k']:>11.4f} "
            f"{_interval(entry['new_design_recall_ci95']):>18}"
        )
    print("\nmodel minus popularity (paired):")
    for name, entry in results["models"].items():
        gap = entry["vs_popularity"]
        print(
            f"{name:<16}recall {gap['recall_diff']:+.4f} {_interval(gap['recall_diff_ci95'])}  "
            f"MAP {gap['map_diff']:+.4f} {_interval(gap['map_diff_ci95'])}  "
            f"new designs {gap['new_design_recall_diff']:+.4f} "
            f"{_interval(gap['new_design_recall_diff_ci95'])}"
        )
    print(f"\nwritten to {args.out}")


if __name__ == "__main__":
    main()
