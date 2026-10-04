<div align="center">

# Fashion App

**A fashion discovery app that learns your style as you swipe — powered by a recommender trained on 31 million real purchases.**

Swipe a feed that adapts to your taste · See *why* each item was picked · Collect what you like and build outfits from it

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Postgres%20%2B%20Auth%20%2B%20Storage-3FCF8E?logo=supabase&logoColor=white)](https://supabase.com/)
[![React Native](https://img.shields.io/badge/React%20Native-Expo-61DAFB?logo=react&logoColor=black)](https://expo.dev/)
[![Status](https://img.shields.io/badge/status-Phase%201%20·%20Data%20and%20model-orange)](#roadmap)

</div>

---

## What it does

| | Feature | How it works |
|---|---|---|
| 🔥 | **Discovery feed** | One card at a time: like or dislike. Every swipe is the only taste signal the system needs — no questionnaire. |
| 🧠 | **Learns your style** | Each garment has 64 learned numbers. Your taste is the average of the ones you like; the feed ranks the catalog by similarity to it. |
| 💡 | **Explains itself** | Every card can show *why* it was surfaced — "because you liked the black hoodie". |
| 👗 | **Wardrobe** | Everything you liked, in one grid. |
| 🧩 | **Outfit sets** | Build 2–5 piece outfits from your wardrobe, one per slot, with a total price. |

*Status: the data pipeline is built; the model, API and app screens are in progress — see the [roadmap](#roadmap).*

## How the recommender works

1. **Data.** The [H&M Personalized Fashion Recommendations](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations) research dataset: ~105k garments and ~31.8M purchases over two years.
2. **Catalog.** 5,000 garments, chosen by per-category quotas (tops, bottoms, dresses, shoes, accessories) and filled with the best-sellers *within the training window* — so every item has enough purchase history to learn from. Articles without a product photo are skipped.
3. **Temporal split.** The model learns from six months of purchases ending 2020-09-08 and is tested on the following two weeks, which it never sees. Splitting by date rather than at random is what stops the evaluation from "seeing the future".
4. **Model.** ALS (alternating least squares) matrix factorisation via the `implicit` library learns 64 latent factors per garment from who bought what. *(In progress.)*
5. **Evaluation.** Simulates a new visitor: three of a real customer's purchases are fed in as likes, and the model must predict the rest of their basket. Scored as recall@12 and MAP@12 against a best-sellers baseline and a random baseline. *(In progress — results will be reported here, whichever way they go.)*

No model runs at request time: vectors are trained offline once, and the API only does arithmetic on the saved numbers (5,000 × 64 floats ≈ 1.3 MB, held in memory).

## Architecture

```
OFFLINE — runs once on a laptop
┌──────────────────────────────────────────────────────────┐
│  H&M dataset  →  select 5,000  →  split by time          │
│              →  train ALS (64 numbers per garment)        │
│              →  evaluate vs best-sellers + random         │
└───────────────┬──────────────────────────────────────────┘
                │ vectors, catalog, photos
LIVE            ▼
┌──────────────────────────────────────────────────────────┐
│       Web app (React Native + Expo, exported to web)      │
│          Feed  ·  Wardrobe  ·  Outfit sets                │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTPS / REST
┌──────────────────────────▼───────────────────────────────┐
│                API (Python · FastAPI)                     │
│   /feed  /interactions  /wardrobe  /outfits  /auth        │
│   Item vectors in memory · style vector rebuilt per call  │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│   Supabase: Postgres (products, vectors, interactions,    │
│   outfits) · Auth incl. guest sessions · Storage (photos) │
└──────────────────────────────────────────────────────────┘
```

No vector database and no cache: at 5,000 items the whole catalog's vectors fit in memory and rank in under a millisecond.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| App | React Native + Expo, TypeScript, Expo Router | One codebase; exported to the web so anyone can try it from a link. |
| API | Python, FastAPI | Async, self-documenting, same language as the ML code. |
| Auth | Supabase Auth (JWT) | Email sign-in now, guest sessions planned so there's no signup wall. Tokens are verified locally when the JWT secret is configured, otherwise by Supabase. |
| Database | Supabase (PostgreSQL) | Products, item vectors, interactions, outfits — with Row Level Security. |
| Photos | Supabase Storage | 5,000 product photos as 400px WebP (~10 KB each). |
| ML | `implicit` (ALS), numpy, pandas, scipy | Trained offline on a CPU in minutes; no inference service needed. |
| CI | GitHub Actions | Type-checks the app and runs the backend test suite on every push; a daily job keeps the free-tier database awake. |

## Repo layout

```
backend/
  app/                       FastAPI app
    main.py                  Entrypoint, middleware, router wiring
    core/config.py           Env-backed settings (single source of env access)
    core/security.py         Access-token verification (local when configured)
    core/errors.py           Distinguishes outages from bad credentials
    api/v1/auth.py           Auth routes
  ml/                        Pure, tested ML logic — no I/O
    constants.py             Shared tunables (one copy, used by evaluation and API)
    selection.py             Catalog selection by category quota
    split.py                 Temporal train/holdout split
    images.py                Photo resizing to WebP
  scripts/                   Thin command-line wrappers that run the pipeline
  tests/                     pytest suite (warnings are treated as errors)
  supabase/schema.sql        Tables, indexes, RLS policies — re-runnable
mobile/                      React Native + Expo app (Expo Router)
landing/                     Static landing page (GitHub Pages)
```

## Quick start

```bash
git clone https://github.com/RohaanPrograms/Fashion-App.git
cd Fashion-App/backend

python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows (PowerShell)
# source .venv/bin/activate       # macOS / Linux

pip install -r requirements-dev.txt   # server + ML + test dependencies
cp .env.example .env                  # then fill in your Supabase keys

python -m pytest -q                   # run the test suite
uvicorn app.main:app --reload         # start the API
```

| | |
|---|---|
| API | http://localhost:8000 |
| Interactive docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

The server itself only needs `requirements.txt`; `requirements-ml.txt` adds the offline training libraries, and `requirements-dev.txt` adds pytest on top. More detail, including the data pipeline commands, in [`backend/README.md`](./backend/README.md).

## API (v1)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/health` | — | Liveness, config and database check |
| `POST` | `/v1/auth/signup` | — | Create account |
| `POST` | `/v1/auth/login` | — | Email/password login |
| `POST` | `/v1/auth/refresh` | — | Swap a refresh token for a fresh access token |
| `GET` | `/v1/auth/me` | Bearer token | Current authenticated user |

Planned: `GET /v1/feed`, `POST /v1/interactions`, `GET /v1/wardrobe`, `GET/POST/DELETE /v1/outfits`.

## Roadmap

**Phase 0 — Foundation** ✅ — FastAPI + Supabase auth, Expo app with token refresh, database schema with RLS, CI, dev/staging/prod config.

**Phase 1 — Data and model** ← in progress

- [x] Acquire the H&M dataset
- [x] Select the 5,000-item catalog (training-window popularity, per-category quotas, photo required)
- [x] Temporal train/holdout split — 4.05M training purchases, 12,103 evaluable test customers
- [x] Schema: `popularity`, `product_code`, `product_vectors`
- [x] Product photos resized to WebP and uploaded to Storage
- [x] Load the catalog into Postgres — 5,000 products with photos and synthetic prices
- [ ] Interaction matrix, ranking functions, metrics
- [ ] Train ALS and evaluate against best-sellers and random baselines

**Phase 2 — Backend:** feed, interactions, wardrobe and outfit endpoints; guest sessions; deploy.
**Phase 3 — App and front door:** feed / wardrobe / sets screens, "why am I seeing this?", web deploy, results in this README.
**Phase 4 — Polish:** visual pass and a demo recording.

**Designed, deliberately not built:** visual search, virtual try-on, affiliate checkout, contextual bandits, trend clustering — each cut for scope, not feasibility.

## Data and licensing

The H&M dataset is licensed for non-commercial research use. This project is a demo, not a store: nothing is sold, prices shown are synthetic, and the dataset itself is never committed to this repository.

---

<div align="center">
<sub>Built by <a href="https://github.com/RohaanPrograms">Rohaan Mirza</a></sub>
</div>
