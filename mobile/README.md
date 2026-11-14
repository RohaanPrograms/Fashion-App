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

## Deploying the web app (Cloudflare Workers)

The web version is a static single-page app: `npx expo export -p web` writes
plain HTML/JS/CSS to `dist/`, and a Cloudflare Worker serves those files
(there is no server code; serving static files is free). `wrangler.jsonc`
holds the Worker's settings. Every push to `main` rebuilds and redeploys it.

Settings in the Cloudflare dashboard (Workers & Pages → `fittfeed` →
Settings → Build):

| Setting | Value |
|---|---|
| Git repository / branch | this repo, `main` |
| Root directory ("Path") | `/mobile` |
| Build command | `EXPO_PUBLIC_ENV=prod npx expo export -p web` |
| Deploy command | `npx wrangler deploy` |
| Build variable | `NODE_VERSION` = `22` (Wrangler needs Node 22.12 or newer) |
| Custom domains | `fittfeed.com`, `www.fittfeed.com` (Settings → Domains & Routes) |

- **`EXPO_PUBLIC_ENV=prod` is in the build command on purpose:** it has to be
  there while the app is built (it picks the live API address), and a
  build-time setting is easy to put in the wrong (runtime) variables list.
- **Reloading on `/wardrobe` works** because `wrangler.jsonc` sets
  `not_found_handling` to `single-page-application`: any address that isn't
  a real file gets `index.html`, and the app picks the screen.
- **CORS:** the API only answers browsers on addresses it lists. The site's
  addresses must be in the API's `CORS_ORIGINS` (Railway → Variables),
  exactly, e.g. `https://fittfeed.com,https://www.fittfeed.com`. Preview
  builds get other addresses that aren't listed, so they can't talk to the API.
- **To test a build locally**, `npx expo serve` does *not* fall back to
  `index.html`, so opening `/wardrobe` directly gives a 404 there (not on
  Cloudflare).
