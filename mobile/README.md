# Fashion App — Mobile (React Native + Expo)

Phase 0: Expo Router navigation with sign up, login, and a placeholder home
screen wired to the backend's `/v1/auth` endpoints.

## Setup

```bash
cd mobile
npm install
cp .env.example .env   # then set EXPO_PUBLIC_API_URL if needed
```

## Run

```bash
npx expo start
```

Then:
- Press `i` for the iOS simulator (macOS only), `a` for an Android emulator, or
- Install **Expo Go** on your phone and scan the QR code.

The app talks to the FastAPI backend, so start that too (`uvicorn app.main:app
--reload` in `backend/`). If you run the app on a real phone, set
`EXPO_PUBLIC_API_URL` to your computer's LAN IP — `localhost` on the phone means
the phone itself, not your computer.

## Environments (dev / staging / prod)

`EXPO_PUBLIC_ENV` selects which backend URL the app points at (see
`src/config.ts`):

| `EXPO_PUBLIC_ENV` | Backend URL                     |
|-------------------|---------------------------------|
| `dev` (default)   | `http://localhost:8000`         |
| `staging`         | your deployed staging API       |
| `prod`            | your deployed production API     |

`EXPO_PUBLIC_API_URL`, if set, always overrides the per-environment default —
use it for the LAN-IP case above.

## Structure

```
app/                 # Expo Router: each file is a screen (a route)
  _layout.tsx        # wraps every screen; redirects based on login state
  index.tsx          # startup splash while the saved session is checked
  login.tsx          # /login
  signup.tsx         # /signup
  home.tsx           # /home  (only reachable when logged in)
src/
  config.ts          # API base URL
  theme.ts           # shared colors + styles
  api/client.ts      # fetch wrapper for the backend
  auth/AuthContext.tsx  # login state shared across the app
```

## Checks

```bash
npx tsc --noEmit     # TypeScript type check (run in CI)
```
