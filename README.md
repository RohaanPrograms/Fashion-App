<div align="center">

# FitFeed

**A fashion feed that learns your taste in three swipes — powered by a recommender trained on 4 million real H&M purchases.**

### [Try it → fittfeed.com](https://fittfeed.com) &nbsp;·&nbsp; [Project page](https://rohaanprograms.github.io/Fashion-App/)

Swipe as a guest, no sign-up · Every card says *why* it was picked · Collect what you like and build outfits from it

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Postgres%20%2B%20Auth%20%2B%20Storage-3FCF8E?logo=supabase&logoColor=white)](https://supabase.com/)
[![React Native](https://img.shields.io/badge/React%20Native-Expo-61DAFB?logo=react&logoColor=black)](https://expo.dev/)
[![Status](https://img.shields.io/badge/status-Phase%203%20·%20Live-brightgreen)](#roadmap)

</div>

---

## Does it work?

About **4× better than best-sellers** at finding what a shopper buys next.

| What ranks the feed | recall@12 | MAP@12 | recall@12, new designs only |
|---|---:|---:|---:|
| **The recommender** (ALS, 128 learned numbers per garment) | **0.146** | **0.075** | **0.091** |
| Best-sellers | 0.033 | 0.010 | 0.027 |
| Random | 0.003 | 0.001 | 0.002 |

**How it was tested.** 8,959 shoppers the model never saw while learning. For each one, their **first 3 purchases in a two-week test period** are fed in as likes, exactly as the app would receive them, and the model must find **the rest of what they bought in that period**.

- **recall@12:** the share of those purchases that appear in the model's top 12.
- **MAP@12:** the same, but it also rewards putting them near the top.
- **New designs only:** leaves out other colours of a design the shopper had already liked, so "the same item in another colour" can't count as a win.

Every gap is well clear of chance: the 95% bootstrap intervals don't overlap (recommender 0.139–0.152, best-sellers 0.030–0.036). All three are scored the way the feed serves them (liked items removed, one colour per design), without the feed's two random "wildcard" slots. Full numbers, every model size tried (32–256 factors), and the paired comparisons are in [`docs/metrics.json`](./docs/metrics.json); the analysis is in [`notebooks/01-model-evaluation.ipynb`](./notebooks/01-model-evaluation.ipynb).

## What it does

| | Feature | How it works |
|---|---|---|
| 🔥 | **Discovery feed** | One card at a time: ✕ dislike, ↷ not sure, ♡ like. Opens straight in as a guest. Best-sellers until your 3rd like, then personalised. |
| 🧠 | **Learns your style** | Each garment has 128 learned numbers. Your taste is the average of the ones you like (minus a little of what you dislike); every garment is ranked by how close it sits. |
| 💡 | **Explains itself** | Tap ⓘ: what the piece is (type, colour, pattern, description) and *why* it's there — "because you liked the black hoodie", with the match score. |
| 🔎 | **Filters** | Categories and garment types, several at once ("T-shirts + Sunglasses"); the feed takes turns between them, each still ranked by your taste. |
| 👗 | **Wardrobe** | Everything you liked, in one grid, filterable by category, type, colour and pattern. Remove items, or start over. |
| 🧩 | **Sets** | Build outfits from your wardrobe, one item per row, with a live total price; edit them any time. |
| ✉️ | **Save your wardrobe** | A guest can add an email (verified with a one-time code) and a password at any time, keeping every swipe. |

## How it works

1. **Data.** The [H&M Personalized Fashion Recommendations](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations) research dataset: ~105k garments and ~31.8M purchases over two years.
2. **Catalogue.** 5,000 garments (2,547 distinct designs), chosen by per-category quotas (tops, bottoms, dresses, shoes, accessories) and filled with the best-sellers *within the training window*, so every item has enough purchase history to learn from. Articles without a photo are skipped.
3. **Split by time.** The model learns from six months of purchases (4.05M) ending 2020-09-08 and is tested on the following two weeks, which it never sees. Splitting by date rather than at random stops the evaluation from "seeing the future".
4. **Model.** ALS (alternating least squares) matrix factorisation via the `implicit` library learns 128 numbers per garment from who bought what: garments bought by the same people end up close together. 128 beat 32, 64 and 256 in the evaluation.
5. **Cold start, as served.** There are no customer vectors at serving time: every visitor is a stranger. Their style is the average of the vectors of what they liked, with dislikes subtracted at a weight of 0.3. The evaluation scores exactly this path, not the textbook one.
6. **Serving.** No model runs at request time. The API holds the 5,000 × 128 vectors in memory (≈ 2.6 MB), rebuilds the visitor's style from their swipes on every request, ranks by cosine similarity, removes what they've swiped and other colours of those designs, keeps one colour per design, and returns 8 top picks plus 2 "wildcards" sampled from their top 100 so the feed doesn't narrow to one lane.

## Limitations

- **A research dataset, not a shop.** Prices are synthetic and nothing can be bought. The H&M data is licensed for non-commercial research only.
- **"Bought together" isn't "goes together".** The model learned from co-purchases, not from what makes a good outfit.
- **The dislike weight (0.3) is a guess.** The dataset has purchases but no dislikes, so it couldn't be learned or validated.
- **Tested offline.** The numbers come from replaying past shoppers, not from live visitors.
- **Mostly womenswear,** because most of the catalogue is.

## Decisions not taken

- **No vector database.** 5,000 × 128 floats is about 2.6 MB: it fits in memory and ranks in milliseconds. A vector database starts to pay off around a million items, and even then pgvector (inside the existing Postgres) would come first.
- **No swipe gesture yet.** Buttons first; the card is built so a gesture can wrap it later without a rewrite.
- **No style quiz.** Cold start is best-sellers until 3 likes: the swipes *are* the quiz.

## Architecture

```
OFFLINE — runs once on a laptop
┌──────────────────────────────────────────────────────────┐
│  H&M dataset  →  select 5,000  →  split by time          │
│              →  train ALS (128 numbers per garment)       │
│              →  evaluate vs best-sellers + random         │
└───────────────┬──────────────────────────────────────────┘
                │ vectors, catalogue, photos
LIVE            ▼
┌──────────────────────────────────────────────────────────┐
│  Web app — React Native + Expo, exported to the web      │
│  Hosted on Cloudflare (fittfeed.com)                     │
│  Feed · Wardrobe · Sets                                   │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTPS / REST
┌──────────────────────────▼───────────────────────────────┐
│  API — Python · FastAPI, hosted on Railway               │
│  Verifies tokens · ranks the feed · enforces the rules   │
│  Item vectors in memory · style rebuilt on every call    │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│  Supabase: Postgres (products, vectors, interactions,     │
│  outfits) · Auth incl. guests + emailed codes · Storage   │
│  (photos, loaded by the app directly)                     │
└──────────────────────────────────────────────────────────┘
```

Every push to `main` runs CI (the backend tests, the app's type check and Jest tests); the API redeploys on Railway only if CI passes, and the web app rebuilds on Cloudflare.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| App | React Native + Expo, TypeScript, Expo Router | One codebase; exported to the web so anyone can try it from a link. |
| Web hosting | Cloudflare Workers (static files) + fittfeed.com | Free, fast, allows commercial use; the custom domain makes a future host move invisible. |
| API | Python, FastAPI on Railway | Same language as the ML code; deploys on every green push. |
| Auth | Supabase Auth (JWT), guest sessions | No sign-up wall. Tokens are verified locally against the project's published keys. |
| Database | Supabase (PostgreSQL) | Products, item vectors, interactions, outfits. |
| Photos | Supabase Storage | 5,000 product photos as 400×600 WebP. |
| ML | `implicit` (ALS), numpy, pandas, scipy | Trained offline on a CPU in minutes; no inference service needed. |
| Tests / CI | pytest (361), Jest (75), GitHub Actions | Real logic (ranking, history, filters, auth, the app's queue and rules) is tested; a daily job keeps the free-tier database awake. |

## API (v1)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/health`, `/health/ready` | — | Liveness; readiness (database reachable, catalogue loaded) |
| `POST` | `/v1/auth/anonymous` | — | Start a guest session (max 5 per IP per hour) |
| `POST` | `/v1/auth/upgrade/start`, `/upgrade/verify`, `/password` | Bearer | Save a guest's account: email a code, verify it (same account id), set a password |
| `POST` | `/v1/auth/login`, `/signup`, `/refresh` | — | Log in, sign up, refresh a session |
| `GET` | `/v1/auth/me` | Bearer | Current user, incl. `is_anonymous` |
| `GET` | `/v1/feed` | Bearer | Next cards with their reasons; `exclude` (cards already held) and `pick` (filters) |
| `GET` | `/v1/feed/filters` | — | The filter buttons: 5 categories with their garment types |
| `GET` | `/v1/products/{id}` | Bearer | One garment |
| `POST` / `DELETE` | `/v1/interactions` | Bearer | Record a like, dislike or skip / start over |
| `GET` / `DELETE` | `/v1/wardrobe`, `/v1/wardrobe/{id}` | Bearer | Liked garments / take one out |
| `GET` / `POST` / `PUT` / `DELETE` | `/v1/outfits`, `/v1/outfits/{id}` | Bearer | Saved sets with computed totals / save / edit / delete |

Every endpoint, with its rules, is in [`backend/README.md`](./backend/README.md); interactive docs are at `/docs` while the server runs.

## Run it yourself

**Backend** (Python 3.13):

```bash
git clone https://github.com/RohaanPrograms/Fashion-App.git
cd Fashion-App/backend

python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows (PowerShell)
# source .venv/bin/activate       # macOS / Linux

pip install -r requirements-dev.txt   # server + ML + test dependencies
cp .env.example .env                  # then fill in your Supabase keys

python -m pytest -q                   # 361 tests
uvicorn app.main:app --reload         # http://localhost:8000/docs
```

**App** (Node 20+):

```bash
cd Fashion-App/mobile
npm install
npx jest                              # 75 tests
npx tsc --noEmit                      # type check
npx expo start                        # then press w for the web version
```

The data pipeline (selecting the catalogue, training, evaluating) is documented step by step in [`backend/README.md`](./backend/README.md); the app's setup and deploy settings are in [`mobile/README.md`](./mobile/README.md).

## Repo layout

```
backend/
  app/                FastAPI app: routes (api/v1), auth and config (core),
                      the in-memory recommender (recs), per-user stores (db)
  ml/                 Pure, tested ML logic: selection, split, ranking, evaluation
  scripts/            Command-line steps of the offline pipeline
  tests/              pytest suite (warnings are treated as errors)
  supabase/schema.sql Tables, indexes, RLS policies — re-runnable
mobile/               The app (Expo Router); tests in __tests__/
landing/              The project page (GitHub Pages)
notebooks/            The model evaluation notebook
docs/metrics.json     The evaluation results
```

## Roadmap

- **Phase 0 — Foundation** ✅ FastAPI + Supabase auth, Expo app, schema with RLS, CI.
- **Phase 1 — Data and model** ✅ Catalogue, time split, ALS at 32–256 factors, cold-start evaluation with bootstrap intervals.
- **Phase 2 — Backend** ✅ Feed, interactions, wardrobe, outfits, guest sessions; deployed on Railway.
- **Phase 3 — App and front door** ✅ Feed / Wardrobe / Sets, "why am I seeing this?", filters, saving a guest's account, live at fittfeed.com, the project page, this README.
- **Next — from tester feedback:** edit a saved set, wardrobe filters, layering in sets, local currency; then a visual polish pass and a demo recording.

**Designed, deliberately not built (yet):** visual search, virtual try-on, affiliate checkout, contextual bandits, trend clustering — each cut for scope, not feasibility.

## Data and licensing

The H&M dataset is licensed for non-commercial research use. This project is a demo, not a store: nothing is sold, prices shown are synthetic, and the dataset itself is never committed to this repository.

---

<div align="center">
<sub>Built by <a href="https://github.com/RohaanPrograms">Rohaan Mirza</a></sub>
</div>
