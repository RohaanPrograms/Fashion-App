# Fashion App — Full Architecture

#fashion #app-architecture #ml #project-planning

> **Status:** Architecture design phase. Solo builder, some CS knowledge, vibe coding approach. Strategy: design the full system, build the MVP slice first.
> **Last updated:** Removed proxy purchasing (legal risk), removed web scraping (legal risk), added discovery feed (swipe mechanic), added virtual try-on (future feature).

---

## What This App Does

A mobile-first fashion app that:
1. Shows a swipeable discovery feed of clothing items — like/dislike/save/cart, with dwell time tracking
2. Learns your style automatically from how you interact with the feed
3. Identifies clothing items from uploaded photos or screenshots
4. Finds alternatives across big brands, small stores, and indie designers
5. Filters everything by your budget
6. Links you directly to the retailer to purchase (affiliate links)
7. *(Future)* Lets you virtually try on clothes using AI

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                Mobile App (React Native + Expo)          │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ Discovery  │  │Visual Search │  │  Wishlist/Cart   │ │
│  │    Feed    │  │(Photo Upload)│  │  + Try-On (V2)   │ │
│  └────────────┘  └──────────────┘  └──────────────────┘ │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTPS / REST
┌──────────────────────────▼──────────────────────────────┐
│                  API Layer (Python FastAPI)               │
│    /feed   /search   /auth   /catalog   /interactions   │
└───┬─────────────┬──────────────┬───────────┬────────────┘
    │             │              │           │
┌───▼──┐   ┌─────▼────┐  ┌──────▼──┐  ┌────▼──────┐
│ Auth │   │   ML     │  │ Catalog │  │ Commerce  │
│      │   │ Service  │  │ Service │  │ Service   │
└───┬──┘   └─────┬────┘  └──────┬──┘  └────┬──────┘
    │            │              │           │
┌───▼────────────▼──────────────▼───────────▼──────────┐
│                        Data Layer                      │
│  Supabase (PostgreSQL + Auth + File Storage)           │
│  Pinecone (vector embeddings)                          │
│  Upstash Redis (caching)                               │
└────────────────────────────────────────────────────────┘
```

---

## Technology Stack — Decisions & Reasoning

### Mobile App
| Decision         | Choice                                                 | Why                                                                                      |
| ---------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| Framework        | React Native + Expo                                    | One codebase for iOS + Android. Expo removes native build complexity. Best for solo dev. |
| Language         | TypeScript                                             | Type safety catches bugs early, especially across API boundaries.                        |
| Navigation       | Expo Router                                            | File-based routing, simpler than React Navigation.                                       |
| State management | Zustand                                                | Lightweight, no boilerplate.                                                             |
| Swipe gestures   | react-native-gesture-handler + react-native-reanimated | Industry standard for gesture-driven UIs. Handles swipe cards smoothly.                  |
| Image handling   | Expo ImagePicker + Camera                              | Built-in, handles permissions, works on both platforms.                                  |
| UI components    | NativeWind (Tailwind for RN)                           | Fast styling, consistent design system.                                                  |
| List rendering   | FlashList (by Shopify)                                 | Significantly faster than FlatList for image-heavy lists.                                |

### Backend API
| Decision | Choice | Why |
|---|---|---|
| Language | Python | ML libraries all live here. Keeps ML and API in the same language. |
| Framework | FastAPI | Async, fast, auto-generates API docs. Industry standard for ML-backed APIs. |
| Auth | Supabase Auth (JWT) | Handles email, OAuth (Google/Apple). No need to build auth from scratch. |

### Databases & Storage
| Store | Technology | What it holds |
|---|---|---|
| Primary DB | Supabase (PostgreSQL) | Users, interactions, catalog metadata, wishlist, cart |
| Vector DB | Pinecone | Style vectors, product embeddings, similarity search |
| Cache | Upstash Redis | Style vectors per user, feed results, session state |
| File storage | Supabase Storage | User-uploaded photos only. Product images referenced by URL. |

### ML Inference
| Subsystem | MVP Approach | Later |
|---|---|---|
| Clothing Vision Model | Replicate API (CLIP ViT-L/14) | Fine-tuned model on fashion data |
| Style Embeddings | HuggingFace Inference API | Self-hosted on Modal |
| Recommendations | Cosine similarity on Pinecone | Contextual bandit |
| Trend Clustering | HDBSCAN batch job (nightly) | Same, larger scale |
| Virtual Try-On | Replicate (IDM-VTON or similar) | Self-hosted inference |

### Infrastructure & Hosting
| Component | Service | Why |
|---|---|---|
| Backend | Railway | Simple GitHub deploys, cheap to start |
| Database | Supabase (managed) | No server to manage |
| ML inference | Replicate | Pay-per-call, no GPU management |
| Cache | Upstash Redis | Serverless, free tier |
| Vector DB | Pinecone | Managed, free starter tier |
| CI/CD | GitHub Actions | Free, deploys on push |
| Monitoring | Sentry + Posthog | Both have generous free tiers |

---

## Layer Deep Dives

### 1. Mobile App Layer

**Four core screens:**
1. **Discovery Feed** — Swipeable clothing items. The primary engagement loop and data source.
2. **Visual Search** — Camera/upload → find alternatives. The core differentiated feature.
3. **Wishlist / Cart** — Saved items, liked items, cart contents.
4. **Profile** — Style preferences, settings, browsing history.

---

### 2. Onboarding Quiz (Before First Feed)

A short style intro shown once — the first time a user opens the app after sign-up. The goal is to bootstrap a rough style vector before they ever see the feed, so the first session feels relevant rather than random.

**Design principles:**
- Maximum 4 screens, completable in under 60 seconds
- Every question maps directly to a cluster seed or filter in the recommendation engine
- No question should feel like a form — visual, tap-based, not text input
- Skippable at any point (some users will refuse, and that's fine — the feed will catch up)

**The 4 screens:**

**Screen 1 — What do you shop for?**
Single-select, large tap targets:
- Women's clothing
- Men's clothing
- Both / no preference

Maps to: catalog filter applied to entire feed.

**Screen 2 — What's your usual budget per item?**
A simple slider or 4 preset ranges:
- Under $30
- $30 – $80
- $80 – $200
- $200+

Maps to: default budget filter pre-set for all searches and feed.

**Screen 3 — Pick styles you're drawn to** *(most important screen)*
A 3×3 grid of aesthetic mood board tiles. User taps all that appeal to them (multi-select). Each tile is a curated image, not a text label.

| Tile | Aesthetic | Maps to cluster |
|---|---|---|
| Clean lines, neutral tones | Minimalist | Cluster A |
| Hoodies, sneakers, graphic tees | Streetwear | Cluster B |
| Blazers, tailored trousers | Smart / Business casual | Cluster C |
| Leggings, sports bras, trainers | Athleisure | Cluster D |
| Flowy fabrics, earthy colours | Boho / Free-spirit | Cluster E |
| Thrifted, retro silhouettes | Vintage / Retro | Cluster F |
| Clean luxury, quiet brands | Quiet luxury | Cluster G |
| Oversized, layered, experimental | Avant-garde / Y2K | Cluster H |
| Simple, everyday basics | Casual / Everyday | Cluster I |

User picks 2–4 tiles. These become their initial cluster memberships with equal weight. The feed immediately draws from those clusters.

**Screen 4 — You're all set**
Brief explanation of the swipe mechanic (3 bullet points, illustration). "Swipe right to like, left to skip. The more you swipe, the better it gets." → Tap to start.

**What happens with quiz data:**
```
Quiz completed
  → Store gender preference + budget range on user profile
  → Selected aesthetic tiles → map to cluster IDs
  → Write initial style_preferences to users table
  → Seed the recommendation engine with cluster weights
  → First feed draws from selected clusters, not global trending
```

**Cold start with quiz vs without:**
- Without quiz: first 10–20 items are global trending → may feel irrelevant → higher early drop-off
- With quiz: first feed is already roughly aligned to stated taste → better first impression → users stay to swipe more

---

### 3. Discovery Feed

This is the TikTok/Reels mechanic applied to fashion. It is the primary ongoing engagement loop and the primary source of behavioural data for the recommendation engine.

**How it works:**
- Items shown one at a time, full-screen (or in a vertical scroll like Reels)
- User can:
  - **Swipe right / tap heart** → Like
  - **Swipe left** → Dislike (do not show again)
  - **Tap bookmark** → Add to wishlist
  - **Tap cart** → Add to cart
  - **Just scroll past** → implicit skip signal
- App tracks **dwell time**: how many milliseconds the user spent looking at each item before acting
- All of this is logged to the interactions table and feeds the recommendation engine in real time

**Why this is architecturally important:**
The discovery feed + onboarding quiz together eliminate the cold start problem. The quiz gives instant signal on day one. The feed then continuously refines the style vector with real behavioural data. Within 10–20 swipes past onboarding, the system has enough to meaningfully personalise.

**Dwell time as a signal:**
Dwell time is more honest than explicit actions. A user might not bother tapping "like" but spending 8 seconds on an item tells you something. Under 1 second = definite skip. 3–8 seconds = interested but not enough. 8+ seconds = strong positive signal.

**Feed rendering:**
```
Session opens
  → Fetch 20 candidate items (ranked by recommendation engine)
  → Pre-load next 5 items in background (smooth scrolling)
  → User interacts → log to interactions table
  → When 10 items remain, fetch next batch
  → Recommendation engine updates style vector after each session
```

**Gesture implementation (React Native):**
Use `react-native-gesture-handler` for swipe detection and `react-native-reanimated` for the card animation. The pattern is well-documented and there are open-source implementations to reference.

---

### 3. API Layer

**Endpoints (v1):**

```
POST   /v1/auth/signup
POST   /v1/auth/login
GET    /v1/auth/me

GET    /v1/feed                        ← Ranked items for discovery feed
POST   /v1/interactions                ← Log a swipe/like/dwell event
GET    /v1/interactions/history        ← User's interaction history

POST   /v1/search/image                ← Upload image → find alternatives
GET    /v1/search/text                 ← Text search with filters

GET    /v1/catalog/item/:id
GET    /v1/catalog/similar/:id

GET    /v1/wishlist
POST   /v1/wishlist
DELETE /v1/wishlist/:id

GET    /v1/cart
POST   /v1/cart
DELETE /v1/cart/:id

GET    /v1/user/profile
PUT    /v1/user/style-preferences
```

**Interaction logging (POST /v1/interactions):**
```json
{
  "product_id": "uuid",
  "type": "like | dislike | wishlist | cart | view | skip",
  "dwell_time_ms": 4200,
  "source": "feed | search | similar"
}
```
This is a high-frequency endpoint. Every swipe hits it. Design it to be fast and non-blocking — write to a queue (Redis) and flush to PostgreSQL in batches.

---

### 4. ML / Intelligence Layer

#### Subsystem 1 — Style Profile Engine
**Goal:** Build a taste fingerprint for each user.

**MVP:** Directly powered by discovery feed interactions. No cold start problem — the feed generates signal from minute one.
- Like = strong positive signal for this item's attributes
- Dislike = strong negative signal
- Dwell time > 5s without action = mild positive signal
- Skip < 1s = mild negative signal

**V2:** Build a proper embedding from interaction sequences. Items the user liked → extract their CLIP embeddings → average them → that's the user's style vector. Store in Pinecone under the user's ID.

**V3:** Self-supervised model trained on sequences (BERT4Rec or item2vec approach). User's interaction history = sentence, items = words. Model learns which items are stylistically related.

---

#### Subsystem 2 — Clothing Vision Model
**Goal:** Given a photo, identify the garment and produce a search embedding.

**MVP:** CLIP via Replicate API.
- Input: image URL
- Output: 512-dimension embedding vector
- Zero-shot classification for category using CLIP's text-image alignment

**V2:** Fine-tune ViT on DeepFashion2 for structured attribute extraction (type, colour, fit, occasion).

**Training data available:** DeepFashion2 (800k+ labeled images), iMaterialist (Kaggle).

---

#### Subsystem 3 — Trend & Cluster Discovery
**Goal:** Surface emerging aesthetics, group users by style.

**MVP:** Skip. Not needed until you have enough users to cluster meaningfully (100+ active users minimum).

**V2:** Run HDBSCAN on product embeddings nightly. Assign aesthetic cluster labels. Use clusters to diversify the feed (prevent filter bubble).

**Implementation:** Python script, scheduled via Railway cron or GitHub Actions.

---

#### Subsystem 4 — Catalog Auto-Tagger
**Goal:** Apply structured attributes to products with no metadata — just an image and a name.

**MVP:** CLIP zero-shot classification. Given a product image, classify against a label list ("jacket", "dress", "navy", "oversized", etc.)

**V2:** Multi-label classifier trained on top of CLIP features.

**Pipeline:** Runs at catalog ingestion time, not real-time.

---

#### Subsystem 5 — Recommendation Engine
**Goal:** Rank the discovery feed for each user.

**MVP:** Cosine similarity between product embeddings and user style vector. No style vector yet on first open → show globally trending items (most liked in last 7 days).

**V2:** Contextual bandit (Vowpal Wabbit or epsilon-greedy). At each session, choose what to show, observe reward, update policy.

**Reward signals (updated with discovery feed data):**

| Signal | Weight | Source |
|---|---|---|
| Purchase (affiliate tap-through) | +10 | Commerce |
| Add to cart | +7 | Discovery feed / search |
| Add to wishlist | +5 | Discovery feed / search |
| Like (swipe right) | +3 | Discovery feed |
| Dwell > 8 seconds | +2 | Discovery feed |
| Dwell 3–8 seconds | +1 | Discovery feed |
| Skip < 1 second | -1 | Discovery feed |
| Dislike (swipe left) | -4 | Discovery feed |

**Filter bubble mitigation:** Reserve 15% of feed slots for items outside the user's current cluster. Expose "browse by aesthetic" section that is not personalised.

---

#### Subsystem 6 — Virtual Try-On *(Future — V2/V3)*
**Goal:** Show the user what a clothing item looks like on them or on a realistic avatar.

**Two approaches, different complexity:**

**Approach A — AI Photo Try-On (V2, feasible)**
User provides one full-body photo of themselves. App uses an AI virtual try-on model to generate a new image of the user wearing the selected item.

- Model: IDM-VTON or CatVTON (both available on Replicate)
- Input: user photo + product image
- Output: generated photo of user in that garment
- Quality is now genuinely good for tops, dresses, outerwear — still imperfect for trousers/shoes
- Processing time: 15–30 seconds (show a loading animation)
- Cost: ~$0.01–0.05 per generation via Replicate

**Approach B — 3D Avatar (V3/V4, very complex)**
User creates a 3D avatar that resembles them (body shape, skin tone, face). Clothing is rendered as 3D on the avatar.

- Requires 3D clothing models — retailers don't provide these
- Body measurement estimation from photo is an unsolved problem at scale
- Avatar creation: ReadyPlayerMe API exists but clothing library is limited
- **Verdict: defer this indefinitely. Approach A gives 80% of the value at 5% of the complexity.**

**Implementation path for Approach A:**
1. Add a "Try On" button on any product detail page
2. First time: prompt user to upload a full-body photo (stored privately in Supabase)
3. Call Replicate API with user photo + product image
4. Display result with a "This is AI-generated" disclaimer
5. User can save or share the result

---

### 5. Catalog Layer

**Data model:**
```
Product {
  id              UUID
  source          string        ← "asos", "farfetch", "etsy", etc.
  source_id       string        ← original product ID at source
  name            string
  brand           string
  url             string        ← affiliate deep link
  price           decimal
  currency        string
  image_url       string        ← source URL (not stored locally)
  in_stock        boolean
  category        string
  attributes      jsonb         ← { colour, fit, occasion, material }
  pinecone_id     string        ← vector ID for similarity search
  created_at      timestamp
  last_synced_at  timestamp
}
```

**Catalog sources — API only, no scraping:**

| Phase | Source | Method |
|---|---|---|
| MVP | ASOS Partner Programme | Affiliate product feed (structured JSON/CSV) |
| MVP | Farfetch API | Luxury + designer brands, official developer API |
| V2 | Etsy API | Handmade, vintage, indie makers |
| V2 | Shopify Storefront API | Thousands of indie/small brands run on Shopify |
| V3 | Direct brand partnerships | Brand submits their own product feed |

**Why no scraping:** Legal risk (ToS violations, potential CFAA exposure), fragile maintenance (sites change constantly), and affiliate APIs give you structured, clean data anyway. The catalog will be smaller initially — that's fine.

**Ingestion pipeline:**
```
Cron job (daily)
  → Fetch new/updated products from affiliate APIs
  → Run CLIP (Replicate) on product image → generate embedding
  → Run Auto-Tagger (Subsystem 4) → extract structured attributes
  → Upsert into PostgreSQL
  → Upsert embedding into Pinecone
```

**Keeping catalog fresh:**
- Full sync daily (prices change, items go OOS)
- Flag out-of-stock rather than delete (needed for trend analysis)
- Check affiliate link health as part of sync

---

### 6. Commerce Layer

**Model: Affiliate Links Only**

User taps a product → app opens the retailer's website via an affiliate deep link → user purchases on the retailer's site → app earns commission.

- No payment processing on your end
- No orders to manage
- No legal liability for fulfillment
- Revenue from day one

**Affiliate networks to join:**
- AWIN (covers ASOS, many high street brands)
- Rakuten Advertising (covers Farfetch, luxury brands)
- ShareASale (covers a wide range of mid-market brands)
- Etsy Affiliate Programme (covers Etsy sellers)
- Direct brand programmes (many DTC brands run their own)

**Commission rates by category:**
- Fast fashion (ASOS, H&M): 4–7%
- Luxury / designer (Farfetch): 6–12%
- Indie / Etsy: 4–8%
- Sportswear: 5–10%

**Future commerce (V2):**
Potentially offer in-app checkout for select brand partners who provide a checkout API. Would require Stripe integration and per-brand agreement. Not a priority until affiliate revenue validates the model.

**No proxy purchasing — ever.** Legal exposure (money transmission, ToS violations, consumer protection liability, 3DS authentication requirements) makes this not worth pursuing.

---

## Data Models (Core Entities)

```sql
-- Users
users (
  id UUID PRIMARY KEY,
  email TEXT,
  created_at TIMESTAMP,
  style_vector_pinecone_id TEXT,   -- reference to their vector in Pinecone
  onboarding_complete BOOLEAN
)

-- Products
products (
  id UUID PRIMARY KEY,
  source TEXT,                     -- "asos", "farfetch", "etsy"
  source_id TEXT,
  name TEXT,
  brand TEXT,
  url TEXT,                        -- affiliate link
  price DECIMAL,
  currency TEXT,
  image_url TEXT,                  -- source URL, not stored locally
  in_stock BOOLEAN,
  category TEXT,
  attributes JSONB,                -- { colour, fit, occasion, material }
  pinecone_id TEXT,
  last_synced_at TIMESTAMP
)

-- Interactions (high-write table — feeds entire recommendation engine)
interactions (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users,
  product_id UUID REFERENCES products,
  type TEXT CHECK (type IN ('like','dislike','wishlist','cart','view','skip')),
  dwell_time_ms INTEGER,           -- milliseconds spent looking at item
  source TEXT CHECK (source IN ('feed','search','similar')),
  created_at TIMESTAMP
)

-- Wishlist
wishlist_items (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users,
  product_id UUID REFERENCES products,
  created_at TIMESTAMP,
  UNIQUE(user_id, product_id)
)

-- Cart
cart_items (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users,
  product_id UUID REFERENCES products,
  created_at TIMESTAMP,
  UNIQUE(user_id, product_id)
)
```

**Note on interactions table:** This will be the highest-write table in the system — every swipe, every second of dwell time. Design the API endpoint to batch-write to Redis first, then flush to PostgreSQL every 30 seconds. Do not write to PostgreSQL on every single interaction at scale.

---

## MVP Definition

**Core hypothesis:** *Will users engage with a discovery feed, and will the visual search find alternatives they actually want?*

Both loops need to be tested together because they complement each other — the feed teaches the app your taste, the search uses that taste to find alternatives.

### MVP Scope

| Include | Exclude |
|---|---|
| Discovery feed (swipe UI) | Virtual try-on |
| Like / dislike / wishlist / cart | Social media connections |
| Dwell time tracking | Trend clustering |
| Basic recommendations (trending) | Full personalisation (needs data first) |
| Visual search (image upload) | Fine-tuned vision model |
| Budget filter | Advanced attribute filtering |
| Affiliate link tap-through | In-app checkout |
| Basic auth (email) | Google/Apple sign-in |
| ASOS + Farfetch catalog | Etsy / Shopify sources |

### MVP User Flow

**Discovery loop:**
```
1. Open app → see discovery feed
2. Swipe through items (like, dislike, wishlist, cart)
3. App quietly builds style profile in background
4. Feed gradually improves
```

**Search loop:**
```
1. Take or upload a photo of a clothing item
2. Set budget range
3. See alternatives from ASOS + Farfetch
4. Tap item → opens retailer site via affiliate link
```

If users return to the feed daily and tap affiliate links, the idea works.

---

## Build Phases

### Phase 0 — Foundation (Weeks 1–2)
- [x] Supabase project: auth, database schema, storage bucket
- [x] FastAPI skeleton with /auth endpoints
- [ ] React Native + Expo app: sign up, login, basic navigation
- [ ] GitHub repo + GitHub Actions CI pipeline
- [ ] Environment config (dev / staging / prod)

### Phase 1 — Discovery Feed + Onboarding (Weeks 3–5)
- [ ] Ingest first 500 products from ASOS affiliate feed
- [ ] Run CLIP embeddings on products → store in Pinecone
- [ ] Onboarding quiz screens (gender, budget, aesthetic tiles)
- [ ] Store quiz results on user profile (gender, budget, cluster seeds)
- [ ] GET /v1/feed endpoint (uses cluster seeds from quiz initially, then interaction history)
- [ ] Swipe card UI in React Native (gesture handler + reanimated)
- [ ] Like / dislike / wishlist / cart interactions
- [ ] Dwell time tracking
- [ ] POST /v1/interactions endpoint (batched writes via Redis)
- [ ] Affiliate link tap-through (opens browser)

### Phase 2 — Visual Search (Weeks 6–8)
- [ ] Image upload → Supabase Storage
- [ ] POST /v1/search/image endpoint
- [ ] CLIP embedding via Replicate
- [ ] Pinecone similarity search
- [ ] Budget filter
- [ ] Results screen with affiliate links
- [ ] Add Farfetch catalog (second source)

### Phase 3 — Personalisation (Weeks 9–12)
- [ ] Style vector construction from interaction history
- [ ] Personalised feed using cosine similarity (user vector ↔ product vectors)
- [ ] Feed visibly improves with more interactions
- [ ] "Because you liked X" labels on feed items
- [ ] Daily sync pipeline for catalog freshness

### Phase 4 — Scale Intelligence (Post-MVP)
- [ ] Contextual bandit recommendation engine (Vowpal Wabbit)
- [ ] Trend / cluster discovery (HDBSCAN nightly job)
- [ ] Catalog auto-tagger for better attribute filtering
- [ ] Etsy + Shopify catalog sources
- [ ] Fine-tune vision model on DeepFashion2
- [ ] Filter bubble mitigation (explore/exploit balance)

### Phase 5 — Virtual Try-On (V2)
- [ ] "Try On" button on product detail page
- [ ] User uploads full-body photo (stored privately)
- [ ] Replicate API call: IDM-VTON model (user photo + product image)
- [ ] Display AI-generated try-on result
- [ ] AI-generated disclaimer
- [ ] Save / share try-on result

### Phase 6 — Commerce Expansion (Later)
- [ ] Google/Apple sign-in
- [ ] In-app checkout for select brand partners (Stripe)
- [ ] Push notifications for wishlist price drops

---

## Open Questions

- [ ] **Affiliate programme approval** — Apply to AWIN and Rakuten early. Some require an existing platform. May need a landing page first. Can take 2–4 weeks.
- [ ] **Apple App Store rules** — Affiliate links that open Safari are generally fine ("reader app" pattern). Confirm before building any in-app commerce.
- [ ] **Discovery feed content at launch** — 500 products is enough to test but the feed will feel repetitive fast. Plan to have at least 5,000 products before any public launch.
- [ ] **Virtual try-on body photo storage** — This is sensitive data. Needs explicit consent, clear privacy policy, and easy deletion. Do not store it without telling users clearly.
- [ ] **Dwell time accuracy on mobile** — iOS/Android background app behaviour can affect timer accuracy. Test this carefully. Use `AppState` API in React Native to pause/resume timers correctly.
- [ ] **Replicate cost at scale** — CLIP inference: ~$0.0002/image. Try-on inference: ~$0.02–0.05/generation. Budget accordingly.
- [ ] **Pinecone index structure** — One index for products + one namespace per user for style vectors, or separate indexes? Decide before building.

---

## Potential Issues & Risks

### Technical Issues

**1. CLIP search results feel irrelevant**
- **Why:** CLIP is a general vision model, not fashion-specific. Struggles with fine-grained attributes (fit, fabric, subtle colour differences).
- **Severity:** Critical — bad search results = users leave immediately.
- **Mitigation:** Pre-filter candidates by category + colour attribute before similarity scoring. Fine-tune on fashion data in V2. Log all low-quality searches for training data.

**2. Slow search response time**
- **Why:** Multiple network hops: upload → Replicate (CLIP) → Pinecone → PostgreSQL.
- **Severity:** High — mobile users expect under 2 seconds.
- **Mitigation:** Show loading animation immediately. Pre-warm Replicate endpoint. Cache embeddings for repeated image uploads.

**3. Affiliate links go dead**
- **Why:** Products go OOS, URLs change, collections get retired.
- **Severity:** Medium — bad UX, erodes trust.
- **Mitigation:** Daily sync checks stock status. Show "may no longer be available" disclaimer on results older than 24 hours. Build dead-link checker into sync job.

**4. Discovery feed performance (React Native)**
- **Why:** Rendering full-screen images in a swipeable stack is GPU-intensive on mid-range Android.
- **Severity:** Medium — jank makes the app feel cheap.
- **Mitigation:** Use FlashList. Pre-load next 3–5 items. Use compressed thumbnails in feed, full resolution only on detail view. Test on a low-end Android from day one.

**5. Dwell time inaccuracy**
- **Why:** iOS and Android can background or throttle apps mid-session. App switching mid-swipe gives false dwell readings.
- **Severity:** Low-Medium — dirty data degrades recommendations slowly.
- **Mitigation:** Use React Native's `AppState` API to pause dwell timer when app goes to background. Cap maximum dwell time at 60 seconds (user left their phone on screen).

**6. Supabase free tier limits**
- **Why:** Free tier: 500MB DB, 1GB file storage, 2GB egress/month.
- **Severity:** Medium — manageable with planning.
- **Mitigation:** Don't store product images in Supabase — use source URLs. Upgrade to Pro ($25/mo) before any real user traffic.

**7. Railway cold starts**
- **Why:** Free/cheap tier spins down idle services. First request takes 15–30 seconds.
- **Severity:** Low for MVP, High with real users.
- **Mitigation:** Use "always on" Railway plan ($5/mo) once you have users. Or keep-alive cron ping every 5 minutes.

---

### ML & Data Issues

**8. Cold start — new users see generic feed**
- **Why:** No interaction history = no style vector = no personalisation.
- **Severity:** Medium — first experience feels random.
- **Mitigation (MVP):** Show globally trending items (most liked in last 7 days). The discovery feed itself generates signal within 10–20 swipes — this is much faster than waiting for purchase history.

**9. Filter bubble**
- **Why:** Recommendation engine converges on narrow aesthetic over time.
- **Severity:** Medium — engagement decays over weeks.
- **Mitigation:** Reserve 15% of feed for items outside user's current cluster. Add "Trending" section that is fully non-personalised. Let users browse by aesthetic manually.

**10. CLIP misidentifies garments**
- **Why:** Flat lays, bad lighting, cropped photos, garments worn under outerwear.
- **Severity:** High if frequent — breaks the core search loop.
- **Mitigation:** Confidence threshold — if top category score < 0.6, ask user to clarify. Log all low-confidence results as training data for V2 fine-tuning.

**11. Embedding drift**
- **Why:** Upgrading the ML model makes old and new embeddings incompatible.
- **Severity:** Low early, High at scale.
- **Mitigation:** Store `embedding_model_version` on every product. Re-embed entire catalog when model changes. Never mix embeddings from different model versions in the same search.

**12. Virtual try-on quality issues**
- **Why:** IDM-VTON and similar models still struggle with complex patterns, trousers, shoes, accessories, and non-standard body positions.
- **Severity:** Medium — users will notice when it looks wrong.
- **Mitigation:** Be upfront: "AI-generated — results may vary." Start with categories the model handles well (tops, dresses, outerwear). Don't offer try-on for categories it handles poorly (trousers, shoes) until quality improves.

---

### Business & Legal Issues

**13. Affiliate programme rejection**
- **Why:** AWIN/Rakuten vet applicants and reject those without established platforms.
- **Severity:** High — no affiliate access = no catalog, no monetisation.
- **Mitigation:** Build a landing page before applying. Apply early (2–4 week approval window). Start with less strict networks (ShareASale, Impact, direct brand programmes).

**14. Apple App Store review**
- **Why:** Apple scrutinises commerce flows heavily. Affiliate links that open Safari are generally fine. Any checkout inside the app triggers in-app purchase rules (30% cut).
- **Severity:** High — can block launch.
- **Mitigation:** MVP uses Safari links only — this is the "reader app" pattern and is App Store compliant. Never build any payment flow inside the app without legal review.

**15. GDPR / Privacy compliance**
- **Why:** Collecting interaction data (swipes, dwell time, images) is personal data under GDPR.
- **Severity:** Medium for MVP, High once you have EU/UK users.
- **Mitigation:** Write a privacy policy before launch. Build DELETE /v1/user/me (data deletion) from day one. Explicit consent for try-on photo storage. Only collect what you need.

**16. Virtual try-on photo sensitivity**
- **Why:** You are storing full-body photos of users. This is sensitive personal data.
- **Severity:** High — a data breach here is catastrophic for trust and legally serious.
- **Mitigation:** Store with encryption at rest. Never use for training data without explicit opt-in consent. Provide one-tap deletion. Make it optional, never required.

**17. Commission attribution failures**
- **Why:** Ad blockers strip tracking parameters. Some browsers block affiliate cookies.
- **Severity:** Medium — industry-wide problem, erodes revenue.
- **Mitigation:** Use deep links that preserve affiliate parameters. Log all tap-through events server-side. Use affiliate networks with server-side (post-back) tracking where available.

---

### Operational Issues

**18. Catalog freshness at scale**
- **Why:** Prices change daily. Items sell out. New collections replace old ones.
- **Severity:** Medium — wrong prices erode trust.
- **Mitigation:** Daily full sync. Prioritise high-traffic items with more frequent checks. Add "Report wrong price" button for users.

**19. Image storage and bandwidth costs**
- **Why:** Product images at scale = large bandwidth costs, especially via S3.
- **Severity:** Medium — manageable with planning.
- **Mitigation:** Reference source image URLs rather than storing copies. Use Cloudflare R2 (zero egress cost) for user-uploaded photos. Serve via CDN.

**20. Solo maintainability**
- **Why:** Fast solo builds accumulate technical debt. One missed abstraction in week 3 becomes load-bearing by week 10.
- **Severity:** Medium — slow burn, not a crisis.
- **Mitigation:** Keep ML logic in isolated Python modules, never mixed into FastAPI route handlers. Use TypeScript throughout the frontend. Use this architecture document as the source of truth — if the AI suggests something that contradicts it, consciously decide which is right before proceeding.

---

## Skills Gap

| Area | Complexity | Approach |
|---|---|---|
| React Native + Expo UI | Medium | Learnable. Expo docs are excellent. |
| Swipe gesture UI (reanimated) | Medium-High | Plenty of open-source examples to reference. |
| FastAPI backend | Medium | Learnable. Python is forgiving. |
| Supabase setup | Low | Good dashboard, clear docs. |
| CLIP / Replicate API | Low | Simple API calls, not ML training. |
| Pinecone integration | Low | SDK is straightforward. |
| Catalog ingestion pipeline | Medium | Python scripting + cron jobs. |
| Dwell time tracking (mobile) | Medium | AppState API + timer logic. Well-documented. |
| Virtual try-on (Replicate) | Low-Medium | API call, but image handling and UX around it takes work. |
| App store deployment | Medium | One-time setup. Expo EAS handles most of it. |
| ML model fine-tuning | High | Defer to V2/V3. Not needed for MVP. |

---

## Cost Breakdown

### The short answer
You can build and test this entire app for **$0/month** during development. The only unavoidable costs come when you want to publish to the App Store, or when you have real users generating real API calls.

---

### Service-by-Service Breakdown

#### Supabase (Database + Auth + Storage)
| Tier | Cost | Limits | Verdict |
|---|---|---|---|
| Free | $0/mo | 500MB DB, 1GB storage, 2GB bandwidth/month | Good for all of development + early users |
| Pro | $25/mo | 8GB DB, 100GB storage, 250GB bandwidth | Upgrade when you launch publicly |

**Free alternative:** PocketBase (self-hosted, free), Firebase (Google — free tier is generous but vendor lock-in risk).

---

#### Pinecone (Vector DB)
| Tier | Cost | Limits | Verdict |
|---|---|---|---|
| Starter (free) | $0/mo | 1 index, 100,000 vectors | Enough for ~100k products — fine for MVP |
| Serverless | ~$0.096/million vectors stored | Pay as you grow | Upgrade when catalog exceeds 100k items |

**Free alternative:** pgvector — a PostgreSQL extension that adds vector search directly inside Supabase. Slower than Pinecone at scale but completely free and zero extra infrastructure. Good enough for MVP if you want to avoid Pinecone entirely at first.

---

#### Replicate (ML Inference — CLIP, virtual try-on)
| Use | Cost per call | At 100 calls/day | At 1,000 calls/day |
|---|---|---|---|
| CLIP embedding (image search) | ~$0.00055 | ~$1.65/mo | ~$16.50/mo |
| IDM-VTON (virtual try-on) | ~$0.05 | ~$150/mo | — |

Replicate has **no free tier** — every call costs money. However, during development you're making very few calls, so it's negligible ($1–5/month while testing).

**Free alternatives:**
- **HuggingFace Inference API** — free tier with rate limits (good for development/testing, not production)
- **Run CLIP locally** — free, but requires a decent GPU or accepts slower CPU inference. Fine for development.
- **Ollama** — run models locally on your machine during dev (completely free)

---

#### Railway (Backend Hosting)
| Tier | Cost | Limits | Verdict |
|---|---|---|---|
| Trial | $5 credit free | Expires, not ongoing | Only for first-time testing |
| Hobby | $5/mo | $5 usage credit included, always-on | Good for development + early users |
| Pro | $20/mo | More resources | When you have real traffic |

**Free alternatives:**
- **Render** — free tier available but service sleeps after 15 min inactivity (same cold start problem as free Railway). $7/mo for always-on.
- **Fly.io** — free tier with 3 shared VMs. More configuration required but genuinely free.
- **Run locally during development** — completely free. Use ngrok to expose your local server to the mobile app during testing.

---

#### Upstash Redis (Caching + interaction queue)
| Tier | Cost | Limits | Verdict |
|---|---|---|---|
| Free | $0/mo | 10,000 commands/day, 256MB | Fine for development and early users |
| Pay-as-you-go | $0.20 per 100k commands | Scales with usage | Very cheap until large scale |

**Free alternative:** Skip Redis entirely for MVP. Write interactions directly to Supabase (acceptable at low volume). Add Redis batching in Phase 3 when you have real traffic.

---

#### Expo + EAS (Mobile App Building)
| Tier | Cost | Limits | Verdict |
|---|---|---|---|
| Free | $0/mo | Unlimited local dev, 30 cloud builds/month | Fine for development |
| EAS Production | $99/year | Unlimited builds, faster queues | Needed for serious app store submissions |

You can develop and test on your own phone for free indefinitely. You only need paid EAS when you're doing frequent App Store submissions.

---

#### App Store Fees (Unavoidable)
| Platform | Cost | Notes |
|---|---|---|
| Apple App Store | $99/year | Required to publish any iOS app. No free alternative. |
| Google Play Store | $25 one-time | Much cheaper. Required to publish on Android. |

**Strategy:** Develop and test on your own devices for free using Expo Go. Only pay for App Store when you're ready to share with real users.

---

#### Other Services (All Free at MVP Scale)
| Service | Free Tier | When You'd Pay |
|---|---|---|
| GitHub | Free (unlimited private repos) | Never, for solo dev |
| GitHub Actions | 2,000 min/month free | If CI pipelines get very long |
| Sentry (error tracking) | 5,000 errors/month free | If you have lots of users crashing |
| Posthog (analytics) | 1M events/month free | Very unlikely to hit this at MVP |
| Domain + landing page | ~$12/year (domain only) | Needed for affiliate programme approval |

---

### Total Cost by Stage

| Stage | Monthly Cost | What you're paying for |
|---|---|---|
| **Development** (just you) | **$0 – $5** | Possibly Railway Hobby ($5/mo). Everything else free. |
| **Testing** (you + a few friends) | **$5 – $15** | Railway + light Replicate usage |
| **Soft launch** (first 100 users) | **$30 – $60** | Railway + Replicate at real usage + Supabase Pro |
| **Real launch** (1,000+ users) | **$100 – $200** | All services at paid tiers, Replicate scales with search volume |

**One-time costs to launch on both app stores: $124** ($99 Apple + $25 Google)

---

### Recommended Free-First Strategy

1. **Development phase:** Run FastAPI locally. Use Expo Go on your phone. Supabase free. Pinecone free. HuggingFace free inference for CLIP testing. Total: **$0/month**.
2. **When you need a real server:** Railway Hobby ($5/mo). Switch Replicate on for real CLIP calls.
3. **When you want to share with testers:** Pay Apple $99 for developer account. Use TestFlight (free, up to 10,000 testers).
4. **When you launch publicly:** Upgrade Supabase to Pro ($25/mo). Everything else scales gracefully.
