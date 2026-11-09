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

## Deploying (Railway)

The API runs on Railway. Railway installs `requirements.txt` only, so the
training libraries are never deployed, and reads the Python version from
`.python-version`. Settings come from Railway's variables, not a file.

In the Railway service's **Settings**:

| Setting | Value |
|---|---|
| Source → Root Directory | `backend` |
| Deploy → Custom Start Command | `/bin/sh -c "exec python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT"` |
| Deploy → Healthcheck Path | `/health/ready` |
| Networking → Public Networking | Generate Domain |

The start command runs through a shell so `$PORT` (chosen by Railway) is
filled in. The health check means a new version only receives traffic once it
can reach Supabase and has loaded the catalogue.

**Variables:**

| Name | Value |
|---|---|
| `APP_ENV` | `prod` |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | the project's values |
| `CORS_ORIGINS` | explicit origins, comma-separated (`*` is refused outside dev) |
| `CLIENT_IP_HEADER` | `X-Real-IP`: where Railway's proxy puts the visitor's IP, used by the guest sign-in limit |

`SUPABASE_JWT_SECRET` is only needed for projects still on Supabase's legacy
HS256 token signing; tokens from the newer signing keys are verified with the
project's published public keys.

Check a deploy end to end (creates one guest account, likes, removes, clears):

```bash
python -m scripts.smoke_test --base-url https://<your-app>.up.railway.app
```

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
    rate_limit.py    # per-IP limit on guest sign-ins
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
