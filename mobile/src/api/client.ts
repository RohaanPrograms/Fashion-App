// A tiny wrapper around fetch() for talking to the FastAPI backend.
// Every network call in the app goes through here so error handling and
// headers live in one place.

import { API_BASE_URL } from "../config";

// Shapes returned by the backend's /v1/auth endpoints.
// These mirror the Pydantic models in backend/app/schemas/auth.py.
// is_anonymous: true for a guest (an account with no email yet).
export type UserOut = { id: string; email?: string | null; is_anonymous: boolean };

export type Session = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in?: number | null;
};

export type AuthResponse = { user: UserOut; session: Session | null };

// Shapes returned by /v1/feed and friends. They mirror backend/app/schemas/
// products.py and feed.py.
export type Product = {
  id: string;
  name: string;
  brand: string | null;
  price: number | null;
  currency: string;
  image_url: string | null;
  category: string | null;
  colour: string | null;
};

// Why a card was picked. "popular": a best-seller (before 3 likes).
// "similar": close to your taste; because_of is the liked item it's nearest
// to. "explore": a deliberate wildcard from your top 100.
export type Reason = {
  kind: "popular" | "similar" | "explore";
  similarity: number | null;
  because_of: { id: string; name: string } | null;
};

export type FeedItem = { product: Product; reason: Reason };

export type FeedResponse = {
  personalised: boolean;
  likes: number;
  likes_needed: number;
  items: FeedItem[];
};

// What we actually keep on the device between app launches.
//
// `expires_at` is the wall-clock time (epoch milliseconds) at which the access
// token stops being accepted. The backend sends a *duration* (`expires_in`,
// e.g. 3600 seconds), which is useless after the app is closed and reopened —
// so we convert it to a fixed point in time the moment we receive it.
export type StoredSession = {
  access_token: string;
  refresh_token: string;
  expires_at: number;
};

// Supabase access tokens last an hour; fall back to that if the server
// doesn't say, so we never treat a token as valid forever.
const DEFAULT_EXPIRES_IN_SECONDS = 3600;

export function toStoredSession(res: AuthResponse): StoredSession | null {
  if (!res.session) return null;
  const lifetimeSeconds = res.session.expires_in ?? DEFAULT_EXPIRES_IN_SECONDS;
  return {
    access_token: res.session.access_token,
    refresh_token: res.session.refresh_token,
    expires_at: Date.now() + lifetimeSeconds * 1000,
  };
}

// A predictable error we throw when the backend responds with a non-2xx status.
export type ApiError = { status: number; detail: string };

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string; // Bearer token for authenticated endpoints
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token } = options;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    // fetch only throws for network-level failures (server down, wrong IP, no wifi).
    throw {
      status: 0,
      detail: `Could not reach the server at ${API_BASE_URL}. Is the backend running?`,
    } as ApiError;
  }

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const detail = data?.detail ?? res.statusText ?? "Request failed";
    throw {
      status: res.status,
      detail: typeof detail === "string" ? detail : JSON.stringify(detail),
    } as ApiError;
  }

  return data as T;
}

export const api = {
  // Not used by the app at the moment: accounts are made by "saving" a guest
  // (upgradeStart/upgradeVerify below). Kept because a traditional
  // confirm-by-link sign-up may come back once the web app has a public
  // address.
  signup: (email: string, password: string) =>
    request<AuthResponse>("/v1/auth/signup", {
      method: "POST",
      body: { email, password },
    }),

  login: (email: string, password: string) =>
    request<AuthResponse>("/v1/auth/login", {
      method: "POST",
      body: { email, password },
    }),

  refresh: (refreshToken: string) =>
    request<AuthResponse>("/v1/auth/refresh", {
      method: "POST",
      body: { refresh_token: refreshToken },
    }),

  me: (token: string) => request<UserOut>("/v1/auth/me", { token }),

  // Start a guest session: a real account with no email. The server allows
  // 5 per network per hour, so the app saves and reuses the one it gets.
  anonymous: () => request<AuthResponse>("/v1/auth/anonymous", { method: "POST" }),

  // "Save your wardrobe", step 1: Supabase emails a one-time code to this address.
  upgradeStart: (token: string, email: string) =>
    request<{ email: string }>("/v1/auth/upgrade/start", {
      method: "POST",
      token,
      body: { email },
    }),

  // Step 2: the code turns the guest into a normal account. Same account id,
  // so every like and set is kept. Returns a fresh session.
  upgradeVerify: (token: string, email: string, code: string) =>
    request<AuthResponse>("/v1/auth/upgrade/verify", {
      method: "POST",
      token,
      body: { email, code },
    }),

  // The next 10 cards. `exclude` = cards the server can't know we already
  // have (on screen, waiting, or swiped but not yet saved). Max 50.
  feed: (token: string, exclude: string[] = []) =>
    request<FeedResponse>(
      `/v1/feed?limit=10${exclude.map((id) => `&exclude=${encodeURIComponent(id)}`).join("")}`,
      { token }
    ),

  // Record a swipe. A like also puts the garment in the wardrobe.
  interact: (token: string, productId: string, type: "like" | "dislike") =>
    request<unknown>("/v1/interactions", {
      method: "POST",
      token,
      body: { product_id: productId, type },
    }),

  // Step 3: give the now-verified account a password, so it can log in.
  setPassword: (token: string, password: string) =>
    request<null>("/v1/auth/password", { method: "POST", token, body: { password } }),
};
