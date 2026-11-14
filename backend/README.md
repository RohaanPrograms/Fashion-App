# Fashion App — Backend (FastAPI)

The API behind the swipe feed (personalised recommendations, saved swipes, a
wardrobe, outfits, guest sign-in) plus the offline ML pipeline that builds the
catalog and trains the ALS recommender whose item vectors the feed ranks.

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

### Emails

The "save your wardrobe" codes are sent by Supabase through **custom SMTP**
(Brevo), configured in Supabase → Authentication → Emails → SMTP Settings, not
in this repo. Supabase's built-in sender only delivers to the project's own team,
so without custom SMTP real visitors would never receive a code. The **Change
Email Address** template must show the code (`{{ .Token }}`): a guest adding an
email is, to Supabase, an email change.

Two Brevo settings this needs, both learned the hard way:
- **Port 2525** (`smtp-relay.brevo.com`). On 587, Supabase stalled for ~40 s per email,
  longer than its gateway waits, so every request failed with 504.
- **Brevo → Security → Authorised IPs: blocking deactivated for SMTP keys.**
  Supabase sends from Amazon servers whose addresses change; with blocking on,
  Brevo refuses them with `525 5.7.1 Unauthorized IP address`.

Check a deploy end to end (creates one guest account, likes, removes, clears):

```bash
python -m scripts.smoke_test --base-url https://<your-app>.up.railway.app
```

## Endpoints (v1)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | none | Liveness: the process is up (never calls out) |
| GET | `/health/ready` | none | Readiness: Supabase reachable and the catalogue loaded |
| POST | `/v1/auth/signup` | none | Create account |
| POST | `/v1/auth/login` | none | Email/password login |
| POST | `/v1/auth/anonymous` | none | Start a guest session (no email); max 5 per visitor IP per hour |
| POST | `/v1/auth/upgrade/start` | Bearer token (guest) | Save a guest's account, step 1: email a one-time code (8 digits on this project) to this address |
| POST | `/v1/auth/upgrade/verify` | Bearer token | Step 2: the code turns the guest into a normal account with the **same id** (every swipe kept); returns a fresh session |
| POST | `/v1/auth/password` | Bearer token (verified) | Step 3: set a password so the account can log in |
| POST | `/v1/auth/refresh` | none | Swap a refresh token for a fresh access token |
| GET | `/v1/auth/me` | Bearer token | Current user, incl. `is_anonymous` |
| GET | `/v1/feed?limit=10&exclude=…&pick=…` | Bearer token | Next cards: best-sellers until 3 likes, then personalised; each card carries its reason and the garment's type, colour, pattern and description. Optional `pick` (repeatable, ≤20): a category (`shoes`) or a garment type (`tops:t-shirts`); several picks take turns, each still ranked by taste. Other colours of a design already swiped (or excluded) are left out |
| GET | `/v1/feed/filters` | — | The filter buttons: 5 categories, each with its garment types |
| GET | `/v1/products/{id}` | Bearer token | One garment's details |
| POST | `/v1/interactions` | Bearer token | Record a like or dislike |
| DELETE | `/v1/interactions` | Bearer token | Start over: forget every swipe |
| GET | `/v1/wardrobe` | Bearer token | Liked garments, most recent first |
| DELETE | `/v1/wardrobe/{product_id}` | Bearer token | Take one out (still counts toward taste; may return to the feed after 20 swipes) |
| GET | `/v1/outfits` | Bearer token | My outfits with computed total prices |
| POST | `/v1/outfits` | Bearer token | Save 2–5 garments, one per slot (a full-body item excludes a top or bottom) |
| DELETE | `/v1/outfits/{id}` | Bearer token | Delete one of my outfits |

The feed's `exclude` lists cards the app already holds, so prefetching the next
batch never resends them. Interactive docs with every request and response
shape are at `/docs` while the server runs.

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
  main.py            # FastAPI app: startup catalogue load, routers, error handler
  core/
    config.py        # env-backed settings (single source of env access)
    security.py      # access-token verification (published ES256 keys, or HS256 secret)
    errors.py        # outage vs bad-credential error mapping
    rate_limit.py    # per-IP limit on guest sign-ins
    supabase_client.py
  recs/              # pure, in-memory recommendation logic
    catalog.py       # 5,000 products + item vectors, loaded once at startup
    history.py       # swipe log -> likes, dislikes, wardrobe, hidden
    feed.py          # picks each batch with ml.ranking, with a reason per card
    outfits.py       # outfit rules and computed totals
  db/                # the only code that reads/writes per-user tables;
    interactions.py  #   every query filters by user_id (tested)
    outfits.py
  api/
    deps.py          # shared dependencies (current user, catalogue, randomness)
    v1/              # auth, feed, interactions, wardrobe, outfits routes
  schemas/           # request/response models
ml/                  # pure functions — the tested core of the pipeline
  constants.py       # shared tunables, one copy for evaluation and API
  selection.py       # catalog selection
  split.py           # temporal train/holdout split
  images.py          # WebP resizing
  matrix.py          # sparse purchase matrix + index mapping
  ranking.py         # style vector, cosine rank, dedupe, exploration (shared with the feed)
  metrics.py         # recall@k, MAP@k
  evaluate.py        # cold-start evaluation against baselines
  train.py           # ALS training
  paging.py          # paging past Supabase's 1,000-row limit (no heavy imports)
scripts/             # command-line wrappers (see Data pipeline), plus smoke_test.py
tests/               # pytest suite
supabase/schema.sql  # tables, indexes, RLS — paste into the SQL Editor; re-runnable
```
