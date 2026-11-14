// App-wide configuration values.
//
// The app can point at three backends depending on which environment this
// build is for. That environment is chosen by EXPO_PUBLIC_ENV:
//
//   EXPO_PUBLIC_ENV=dev      -> http://localhost:8000   (default)
//   EXPO_PUBLIC_ENV=staging  -> your deployed staging API
//   EXPO_PUBLIC_ENV=prod     -> your deployed production API
//
// (Variables must start with EXPO_PUBLIC_ to be readable from app code.)
//
// Set it in a `.env` file in the mobile/ folder, e.g.:
//   EXPO_PUBLIC_ENV=staging

export type AppEnv = "dev" | "staging" | "prod";

// Read the requested environment, defaulting to dev, and guard against typos.
const requested = (process.env.EXPO_PUBLIC_ENV ?? "dev") as AppEnv;
export const APP_ENV: AppEnv = ["dev", "staging", "prod"].includes(requested)
  ? requested
  : "dev";

// Default backend URL for each environment. There is no separate staging
// deployment; staging and prod both use the live API on Railway. The web
// build on Cloudflare Pages sets EXPO_PUBLIC_ENV=prod.
const LIVE_API = "https://fashion-app-production-fb70.up.railway.app";
const API_URL_BY_ENV: Record<AppEnv, string> = {
  dev: "http://localhost:8000",
  staging: LIVE_API,
  prod: LIVE_API,
};

// The base URL of the FastAPI backend for the selected environment.
//
// EXPO_PUBLIC_API_URL, if set, ALWAYS wins. This is the escape hatch for
// testing on a real phone through Expo Go: "localhost" there means the PHONE,
// not your computer, so set your computer's LAN IP instead, e.g.
//   EXPO_PUBLIC_API_URL=http://192.168.1.42:8000
// (find it with `ipconfig` on Windows — look for "IPv4 Address").
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL ?? API_URL_BY_ENV[APP_ENV];
