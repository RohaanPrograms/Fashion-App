"""Stage 3 CLI — resize the catalog's photos and upload them to Storage.

    cd backend
    python -m scripts.prepare_images --images-dir ../data/hm/images \
        --subset ../data/subset.csv --work-dir ../data/webp

Uploads run 8 at a time: 5,000 one-by-one round trips would take most of an
hour. Re-running is safe — converted files are reused and uploads overwrite.
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.core.supabase_client import get_service_client
from ml.images import resize_to_webp
from scripts.hm_data import kaggle_image_name

MAX_WIDTH = 400
UPLOAD_WORKERS = 8
MAX_ATTEMPTS = 4
# Photos are keyed by article ID and never change, so browsers may keep them
# for a year — repeat visits then cost no Storage bandwidth.
CACHE_SECONDS = "31536000"


def _upload(client, bucket: str, article_id: str, path: Path) -> None:
    data = path.read_bytes()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # A fresh options dict each call: the library pops keys out of it.
            client.storage.from_(bucket).upload(
                f"{article_id}.webp",
                data,
                {"content-type": "image/webp", "upsert": "true",
                 "cache-control": CACHE_SECONDS},
            )
            return
        except Exception:
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(2 ** attempt)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", required=True, type=Path)
    parser.add_argument("--subset", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args()

    bucket = get_settings().PRODUCT_IMAGE_BUCKET
    if not bucket:
        raise SystemExit("Set PRODUCT_IMAGE_BUCKET in backend/.env first.")

    article_ids = list(pd.read_csv(args.subset, dtype={"article_id": str})["article_id"])

    converted: list[tuple[str, Path]] = []
    missing: list[str] = []
    for article_id in article_ids:
        source = args.images_dir / kaggle_image_name(article_id).removeprefix("images/")
        if not source.exists():
            missing.append(article_id)
            continue
        dest = args.work_dir / f"{article_id}.webp"
        if not dest.exists():
            resize_to_webp(source, dest, MAX_WIDTH)
        converted.append((article_id, dest))

    total_kb = sum(p.stat().st_size for _, p in converted) / 1024
    print(f"converted {len(converted)} ({total_kb / 1024:.0f} MB, "
          f"avg {total_kb / max(len(converted), 1):.0f} KB); missing source photo: {len(missing)}")
    if missing:
        raise SystemExit("Run scripts.fetch_images first: " + ", ".join(missing[:10]))

    client = get_service_client()
    started = time.time()
    with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as pool:
        futures = [pool.submit(_upload, client, bucket, a, p) for a, p in converted]
        for done, future in enumerate(as_completed(futures), start=1):
            future.result()
            if done % 500 == 0:
                print(f"  uploaded {done}/{len(converted)} ({time.time() - started:.0f}s)")

    print(f"done: {len(converted)} images in bucket '{bucket}'")


if __name__ == "__main__":
    main()
