"""Fetch the catalog's product photos by having Kaggle zip them for us.

    cd backend
    python -m scripts.kaggle_bundle_images --subset ../data/subset.csv \
        --images-dir ../data/hm/images

The photos live on Kaggle (tens of GB; we need ~5,000). Downloading them one
request each runs into Kaggle's API rate limit, so instead this:

  1. uploads subset.csv to your account as a PRIVATE dataset,
  2. pushes a PRIVATE notebook that copies those photos into one zip on
     Kaggle's own machines, where the photos already are,
  3. waits for it, then downloads and unpacks the single zip.

About a dozen API requests in total. Both items can be deleted from your
Kaggle account afterwards; re-running creates new versions of them.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

import pandas as pd
from kaggle.api.kaggle_api_extended import KaggleApi

from scripts.hm_data import KAGGLE_COMPETITION

DATASET_SLUG = "fashion-app-catalog-subset"
KERNEL_SLUG = "fashion-app-bundle-images"
ZIP_NAME = "subset_images.zip"
POLL_SECONDS = 30
TIMEOUT_SECONDS = 45 * 60

# Runs on Kaggle. Inputs are mounted under /kaggle/input; the exact folder
# names vary, so it searches a few levels down for the two files it needs.
KERNEL_CODE = f'''
import zipfile
from pathlib import Path

import pandas as pd

INPUT = Path("/kaggle/input")


def find(name):
    for pattern in ("*/" + name, "*/*/" + name, "*/*/*/" + name):
        hits = sorted(INPUT.glob(pattern))
        if hits:
            return hits[0]
    raise FileNotFoundError(name)


subset = pd.read_csv(find("subset.csv"), dtype={{"article_id": str}})
images = find("articles.csv").parent / "images"
found, missing = 0, []
# Photos are already JPEG-compressed, so store them without recompressing.
with zipfile.ZipFile("/kaggle/working/{ZIP_NAME}", "w", zipfile.ZIP_STORED) as bundle:
    for article_id in subset["article_id"]:
        source = images / article_id[:3] / (article_id + ".jpg")
        if source.exists():
            bundle.write(source, article_id[:3] + "/" + article_id + ".jpg")
            found += 1
        else:
            missing.append(article_id)
print("bundled", found, "missing", len(missing), missing[:20])
'''


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _dataset_exists(api: KaggleApi, ref: str) -> bool:
    try:
        api.dataset_status(ref)
        return True
    except Exception:
        return False


def upload_subset(api: KaggleApi, user: str, subset: Path) -> str:
    ref = f"{user}/{DATASET_SLUG}"
    with tempfile.TemporaryDirectory() as folder:
        shutil.copy(subset, Path(folder) / "subset.csv")
        _write_json(Path(folder) / "dataset-metadata.json", {
            "title": DATASET_SLUG,
            "id": ref,
            "licenses": [{"name": "CC0-1.0"}],
        })
        if _dataset_exists(api, ref):
            response = api.dataset_create_version(
                folder, version_notes="updated catalog subset", quiet=True,
                delete_old_versions=True,
            )
        else:
            response = api.dataset_create_new(folder, public=False, quiet=True)
    if getattr(response, "error", None):
        raise SystemExit(f"Kaggle refused the dataset upload: {response.error}")

    for _ in range(40):
        time.sleep(15)
        # A just-created private dataset briefly answers 403 while Kaggle sets
        # up its permissions, so an error here means "not ready yet".
        try:
            if str(api.dataset_status(ref)).lower() == "ready":
                return ref
        except Exception:
            pass
    raise SystemExit(f"Dataset {ref} never became ready")


def run_kernel(api: KaggleApi, user: str, dataset_ref: str) -> str:
    ref = f"{user}/{KERNEL_SLUG}"
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "bundle.py").write_text(KERNEL_CODE, encoding="utf-8")
        _write_json(Path(folder) / "kernel-metadata.json", {
            "id": ref,
            "title": KERNEL_SLUG,
            "code_file": "bundle.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": False,
            "enable_internet": False,
            "dataset_sources": [dataset_ref],
            "competition_sources": [KAGGLE_COMPETITION],
            "kernel_sources": [],
        })
        response = api.kernels_push(folder)
    if getattr(response, "error", None):
        raise SystemExit(f"Kaggle refused the notebook: {response.error}")

    started = time.time()
    time.sleep(POLL_SECONDS)
    while time.time() - started < TIMEOUT_SECONDS:
        result = api.kernels_status(ref)
        status = str(getattr(result, "status", result)).lower()
        print(f"  notebook status: {status} ({time.time() - started:.0f}s)", flush=True)
        if "complete" in status:
            return ref
        if "error" in status or "cancel" in status:
            message = getattr(result, "failure_message", "")
            raise SystemExit(f"Notebook failed: {message} — see {ref} on Kaggle")
        time.sleep(POLL_SECONDS)
    raise SystemExit("Notebook did not finish in time")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", required=True, type=Path)
    parser.add_argument("--images-dir", required=True, type=Path)
    args = parser.parse_args()

    api = KaggleApi()
    api.authenticate()
    user = api.config_values["username"]

    print("1/3 uploading subset.csv as a private dataset...", flush=True)
    dataset_ref = upload_subset(api, user, args.subset)

    print("2/3 running the private bundling notebook on Kaggle...", flush=True)
    kernel_ref = run_kernel(api, user, dataset_ref)

    print("3/3 downloading and unpacking the zip...", flush=True)
    with tempfile.TemporaryDirectory() as folder:
        api.kernels_output(kernel_ref, folder, file_pattern=ZIP_NAME, force=True)
        archive = Path(folder) / ZIP_NAME
        args.images_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(args.images_dir)

    wanted = pd.read_csv(args.subset, dtype={"article_id": str})["article_id"]
    absent = [a for a in wanted if not (args.images_dir / a[:3] / f"{a}.jpg").exists()]
    print(f"{len(wanted) - len(absent)} of {len(wanted)} catalog photos on disk")
    if absent:
        raise SystemExit("still missing: " + ", ".join(absent[:20]))


if __name__ == "__main__":
    main()
