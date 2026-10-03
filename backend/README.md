# Fashion App — Backend (FastAPI)

The API (config, Supabase wiring, `/auth`, `/health`) plus the offline ML
pipeline that builds the catalog and, next, trains the recommender.

## Setup

```bash
cd backend
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env   # then fill in Supabase keys
```

Three dependency files, each building on the last:

| File | Adds | Needed for |
|---|---|---|
| `requirements.txt` | FastAPI, Supabase, numpy | running the API (all the server installs) |
| `requirements-ml.txt` | pandas, scipy, implicit, Pillow, pyarrow, kaggle | the offline data pipeline and training |
| `requirements-dev.txt` | pytest | running the tests |

## Tests

```bash
python -m pytest -q
```

The suite stubs Supabase, so it needs no credentials or network. `pytest.ini`
turns warnings into failures on purpose, so a deprecation is noticed rather than
ignored. CI runs the same command on every push.

## Run

```bash
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

The app boots without Supabase credentials. Auth endpoints return `503`
until `SUPABASE_URL` / `SUPABASE_ANON_KEY` are set in `.env`.

## Environments (dev / staging / prod)

`APP_ENV` selects which env file the app loads at startup:

| `APP_ENV` | File loaded      | Template                |
|-----------|------------------|-------------------------|
| `dev`     | `.env` (default) | `.env.example`          |
| `staging` | `.env.staging`   | `.env.staging.example`  |
| `prod`    | `.env.prod`      | `.env.prod.example`     |

```bash
# Windows (PowerShell)
$env:APP_ENV = "staging"; uvicorn app.main:app
# macOS/Linux
APP_ENV=prod uvicorn app.main:app
```

Startup fails loudly if `APP_ENV` is unknown, or if `CORS_ORIGINS` is `*`
outside dev. `GET /health` echoes the active `environment`.

## Endpoints (v1)

| Method | Path             | Auth        | Purpose                       |
|--------|------------------|-------------|-------------------------------|
| GET    | `/health`        | none        | Liveness + config check       |
| POST   | `/v1/auth/signup`| none        | Create account                |
| POST   | `/v1/auth/login` | none        | Email/password login          |
| POST   | `/v1/auth/refresh`| none       | Swap a refresh token for a fresh access token |
| GET    | `/v1/auth/me`    | Bearer token| Current authenticated user    |

Access tokens expire after one hour. The mobile app stores the refresh token
returned by login/signup and calls `/v1/auth/refresh` automatically just before
expiry, so users stay signed in. A `401` from that endpoint means the refresh
token itself is dead and the user must log in again.

## Data pipeline

Offline, run once, in order. Input and output live in `../data/`, which is
git-ignored: the H&M data is several GB and licensed for non-commercial
research use, so it is never committed.

**Prerequisites:** a Kaggle account with the
[competition](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations)
rules accepted, an API token at `~/.kaggle/kaggle.json`, and `articles.csv` and
`transactions_train.csv` downloaded into `../data/hm/`. For the photo upload,
a **public** Storage bucket named in `PRODUCT_IMAGE_BUCKET`.

```bash
# 1. Which articles have a product photo (~10 min; Kaggle rate-limits listing)
python -m scripts.list_image_ids --out ../data/image_ids.txt

# 2. Choose the 5,000-item catalog: per-category quotas, filled by
#    training-window popularity, photo required
python -m scripts.select_subset --data-dir ../data/hm \
    --image-ids ../data/image_ids.txt --out ../data/subset.csv

# 3. Split purchases by date into train.parquet / holdout.parquet
python -m scripts.build_training_set --data-dir ../data/hm \
    --subset ../data/subset.csv --out-dir ../data

# 4. Fetch the catalog's photos — a private Kaggle notebook zips them
#    (creates a private dataset + notebook in your Kaggle account)
python -m scripts.kaggle_bundle_images --subset ../data/subset.csv \
    --images-dir ../data/hm/images

# 5. Resize to 400px WebP and upload to Supabase Storage, 8 at a time
python -m scripts.prepare_images --images-dir ../data/hm/images \
    --subset ../data/subset.csv --work-dir ../data/webp
```

Every step is safe to re-run. The 31.8M-row purchases file is read with
categorical and integer types (~0.6 GB of RAM rather than ~6 GB as text).

## Layout

```
app/
  main.py            # FastAPI app + middleware + router wiring
  core/
    config.py        # env-backed settings (single source of env access)
    security.py      # access-token verification
    errors.py        # outage vs bad-credential error mapping
    supabase_client.py
  api/
    deps.py          # shared dependencies (current-user resolver)
    v1/auth.py       # auth routes
  schemas/auth.py    # request/response models
ml/                  # pure functions, no I/O — the tested core of the pipeline
  constants.py       # shared tunables, one copy for evaluation and API
  selection.py       # catalog selection
  split.py           # temporal train/holdout split
  images.py          # WebP resizing
scripts/             # command-line wrappers around ml/ (see Data pipeline)
tests/               # pytest suite
supabase/schema.sql  # tables, indexes, RLS — paste into the SQL Editor; re-runnable
```
