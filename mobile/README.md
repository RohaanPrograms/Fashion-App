# Fashion App — App (React Native + Expo, web first)

The swipe app: open it and you're straight into a feed of clothes, as a guest.
Like (♡), dislike (✕) or skip (↷) each card; after 3 likes the feed is
personalised. Likes land in the Wardrobe, and the Sets tab builds outfits
from it. A guest can save their wardrobe with an email at any time.

Live at **https://fittfeed.com**.

## Setup

```bash
cd mobile
npm install
cp .env.example .env   # then set EXPO_PUBLIC_API_URL if needed
```

## Run

```bash
npx expo start         # then press w for the web version
```

Or press `a` for an Android emulator, `i` for the iOS simulator (macOS only),
or scan the QR code with **Expo Go** on a phone.

The app talks to the FastAPI backend, so start that too (`uvicorn app.main:app
--reload` in `backend/`). If you run the app on a real phone, set
`EXPO_PUBLIC_API_URL` to your computer's LAN IP — `localhost` on the phone means
the phone itself, not your computer.

## Environments (dev / staging / prod)

`EXPO_PUBLIC_ENV` selects which backend URL the app points at (see
`src/config.ts`):

| `EXPO_PUBLIC_ENV` | Backend URL                                          |
|-------------------|------------------------------------------------------|
| `dev` (default)   | `http://localhost:8000`                              |
| `staging`         | `https://fashion-app-production-fb70.up.railway.app` |
| `prod`            | `https://fashion-app-production-fb70.up.railway.app` |

There is no separate staging API; staging and prod both use the live one.
`EXPO_PUBLIC_API_URL`, if set, always overrides the per-environment default —
use it for the LAN-IP case above.

## Structure

```
app/                     # Expo Router: each file is a screen (a route)
  _layout.tsx            # wraps every screen; the login gate; desktop phone frame
  index.tsx              # start-up: opens as a guest, or "Couldn't start"
  login.tsx              # /login
  save.tsx               # /save: a guest saves their wardrobe (email, code, password)
  (tabs)/                # the tab bar (the folder name isn't in the address)
    feed.tsx             # /feed: filters, one card at a time, ⓘ panel
    wardrobe.tsx         # /wardrobe: liked items; remove; start over
    outfits.tsx          # /outfits: saved sets
  outfits/new.tsx        # /outfits/new: the set builder
src/
  config.ts              # API base URL per environment
  theme.ts               # shared colours + styles
  format.ts              # prices
  api/                   # fetch wrapper for the backend; one retry for swipes
  auth/                  # login state, guest start-up
  feed/                  # feed queue, progress, filters, the "why" text
  outfits/builder.ts     # set-builder rules (mirror the server's)
  components/            # card, tiles, filter bar, buttons, phone frame
__tests__/               # Jest tests for the pure logic in src/
```

## Checks

```bash
npx tsc --noEmit     # TypeScript type check (run in CI)
npx jest             # tests for the pure logic (run in CI)
```

## Deploying the web app (Cloudflare Pages)

The web version is a static single-page app: `npx expo export -p web` writes
plain HTML/JS/CSS to `dist/`, and Cloudflare Pages serves it. Every push to
`main` rebuilds it. Settings, in the Cloudflare dashboard (Workers & Pages →
the project → Settings):

| Setting | Value |
|---|---|
| Production branch | `main` |
| Root directory | `mobile` |
| Build command | `npx expo export -p web` |
| Build output directory | `dist` |
| Environment variable | `EXPO_PUBLIC_ENV` = `prod` |
| Environment variable | `NODE_VERSION` = `22` |
| Custom domain | `fittfeed.com` (and `www.fittfeed.com`) |

- **No routing file is needed.** With no `404.html` in `dist/`, Cloudflare
  Pages treats the site as a single-page app and serves `index.html` for every
  address, so reloading on `/wardrobe` works.
- **CORS:** the API only answers browsers on addresses it lists. The site's
  address must be in the API's `CORS_ORIGINS` (Railway → Variables), exactly,
  e.g. `https://fittfeed.com,https://www.fittfeed.com`. Cloudflare's per-change
  preview addresses aren't listed, so previews can't talk to the API.
- **To test a build locally**, `npx expo serve` does *not* fall back to
  `index.html`, so opening `/wardrobe` directly gives a 404 there (not on
  Cloudflare).
