"""List which H&M articles have a product photo, without downloading any.

    cd backend
    python -m scripts.list_image_ids --out ../data/image_ids.txt

A few hundred articles have no photo — including some best-sellers — so
catalog selection reads this list and skips them. Kaggle rate-limits this
endpoint, so a 429 response waits and retries the same page.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi

from scripts.hm_data import KAGGLE_COMPETITION

PAGE_SIZE = 1000
MAX_WAIT_SECONDS = 300


def _list_page(api: KaggleApi, token: str | None):
    wait = 15
    while True:
        try:
            return api.competition_list_files(
                KAGGLE_COMPETITION, page_token=token, page_size=PAGE_SIZE
            )
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status != 429 or wait > MAX_WAIT_SECONDS:
                raise
            print(f"  rate-limited; waiting {wait}s", flush=True)
            time.sleep(wait)
            wait *= 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    api = KaggleApi()
    api.authenticate()

    ids: list[str] = []
    token = None
    pages = 0
    while True:
        response = _list_page(api, token)
        for f in response.files:
            if f.name.startswith("images/") and f.name.endswith(".jpg"):
                ids.append(Path(f.name).stem)
        pages += 1
        if pages == 1 or pages % 20 == 0:
            print(f"  {pages} pages ({len(response.files)} per page), "
                  f"{len(ids):,} photos so far", flush=True)
        token = response.next_page_token
        if not token:
            break

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(sorted(ids)) + "\n", encoding="utf-8")
    print(f"{len(ids):,} articles have a photo -> {args.out}")


if __name__ == "__main__":
    main()
