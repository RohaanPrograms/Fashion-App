<div align="center">

# Fashion App

**A mobile-first fashion discovery app that learns your style as you swipe.**

Swipe a feed that adapts to your taste · Point your camera at any outfit to find it · Filter everything by your budget

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Postgres%20%2B%20Auth-3FCF8E?logo=supabase&logoColor=white)](https://supabase.com/)
[![React Native](https://img.shields.io/badge/React%20Native-Expo-61DAFB?logo=react&logoColor=black)](https://expo.dev/)
[![Status](https://img.shields.io/badge/status-Phase%200%20·%20Foundation-orange)](#roadmap)

</div>

---

## What it does

| | Feature | How it works |
|---|---|---|
| 🔥 | **Discovery feed** | Swipe to like, dislike, save, or cart. Dwell time is tracked as an implicit signal. |
| 🧠 | **Learns your style** | Interactions build a style vector — no questionnaire, no manual tagging. |
| 📸 | **Visual search** | Upload a photo or screenshot; the app identifies the garment. |
| 🔎 | **Finds alternatives** | Matches across big brands, small stores, and indie designers. |
| 💸 | **Budget filtering** | Every surface respects the price range you set. |
| 🔗 | **Tap to buy** | Links straight to the retailer via affiliate links. |
| ✨ | **Virtual try-on** | *Planned.* AI try-on from a single photo. |

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│              Mobile App (React Native + Expo)            │
│    Discovery Feed  ·  Visual Search  ·  Wishlist/Cart    │
└─────────────────────────┬────────────────────────────────┘
                          │ HTTPS / REST
┌─────────────────────────▼────────────────────────────────┐
│                 API Layer (Python · FastAPI)             │
│      /feed   /search   /auth   /catalog   /interactions  │
└───┬──────────────┬──────────────┬───────────┬────────────┘
    │              │              │           │
┌───▼───┐   ┌──────▼─────┐  ┌─────▼────┐  ┌───▼───────┐
│ Auth  │   │ ML Service │  │ Catalog  │  │ Commerce  │
└───┬───┘   └──────┬─────┘  └─────┬────┘  └───┬───────┘
    │              │              │           │
┌───▼──────────────▼──────────────▼───────────▼───────────┐
│                       Data Layer                        │
│  Supabase (Postgres · Auth · Storage)                   │
│  Pinecone (vector embeddings)  ·  Upstash Redis (cache) │
└─────────────────────────────────────────────────────────┘
```

[`fashion-app-architecture.md`](./fashion-app-architecture.md) is the source of truth — stack decisions, data model, ML pipeline, and phasing all live there.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Mobile | React Native + Expo, TypeScript, Zustand, NativeWind | One codebase for iOS and Android, minimal native build complexity. |
| API | Python, FastAPI | Async, self-documenting, and in the same language as the ML stack. |
| Auth | Supabase Auth (JWT) | Email plus Google/Apple OAuth without building auth from scratch. |
| Database | Supabase (PostgreSQL) | Users, interactions, catalog metadata, wishlist, cart. |
| Vectors | Pinecone | Style vectors and product embeddings for similarity search. |
| Cache | Upstash Redis | Per-user style vectors, feed results, session state. |
| ML | Replicate (CLIP ViT-L/14), HuggingFace Inference | Hosted inference for the MVP; self-hosted later. |

## Repo layout

```
backend/                     FastAPI backend — auth, feed, search, catalog APIs
  app/
    main.py                  App entrypoint, middleware, router wiring
    core/config.py           Env-backed settings (single source of env access)
    core/supabase_client.py  Supabase client
    api/deps.py              Shared dependencies (current-user resolver)
    api/v1/auth.py           Auth routes
    schemas/auth.py          Request/response models
mobile/                      React Native + Expo app          (not yet created)
fashion-app-architecture.md  Full design doc — the source of truth
```

## Quick start

```bash
git clone https://github.com/RohaanPrograms/Fashion-App.git
cd Fashion-App/backend

python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows (PowerShell)
# source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
cp .env.example .env              # then fill in your Supabase keys

uvicorn app.main:app --reload
```

| | |
|---|---|
| API | http://localhost:8000 |
| Interactive docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

The app boots without Supabase credentials. Auth endpoints return `503` until `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set in `.env`.

More detail in [`backend/README.md`](./backend/README.md).

## API (v1)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/health` | — | Liveness and config check |
| `POST` | `/v1/auth/signup` | — | Create account |
| `POST` | `/v1/auth/login` | — | Email/password login |
| `GET` | `/v1/auth/me` | Bearer token | Current authenticated user |

## Roadmap

**Phase 0 — Foundation** (weeks 1–2) ← we are here

- [x] Repo structure and environment config
- [x] FastAPI skeleton with `/auth` endpoints
- [x] React Native + Expo app: signup, login, navigation
- [x] Supabase project: auth, schema, storage bucket
- [x] GitHub Actions CI pipeline

| Phase | | Highlights |
|---|---|---|
| 1 | **Discovery Feed + Onboarding** <sub>weeks 3–5</sub> | First 500 products ingested, CLIP embeddings into Pinecone, swipe card UI, interaction + dwell-time tracking |
| 2 | **Visual Search** <sub>weeks 6–8</sub> | Image upload, `POST /v1/search/image`, Pinecone similarity, budget filter, second catalog source |
| 3 | **Personalisation** <sub>weeks 9–12</sub> | Style vectors from interaction history, cosine-similarity feed, "because you liked X" |
| 4 | **Scale Intelligence** <sub>post-MVP</sub> | Contextual bandit, HDBSCAN trend clustering, fine-tuned vision model, filter-bubble mitigation |
| 5 | **Virtual Try-On** <sub>v2</sub> | IDM-VTON via Replicate, private photo storage, save and share results |
| 6 | **Commerce Expansion** <sub>later</sub> | Google/Apple sign-in, in-app Stripe checkout, wishlist price-drop alerts |

Full breakdown in [`fashion-app-architecture.md`](./fashion-app-architecture.md#build-phases).

---

<div align="center">
<sub>Built by <a href="https://github.com/RohaanPrograms">Rohaan Mirza</a></sub>
</div>
