// A tiny wrapper around fetch() for talking to the FastAPI backend.
// Every network call in the app goes through here so error handling and
// headers live in one place.

import { API_BASE_URL } from "../config";

// Shapes returned by the backend's /v1/auth endpoints.
// These mirror the Pydantic models in backend/app/schemas/auth.py.
export type UserOut = { id: string; email?: string | null };

export type Session = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in?: number | null;
};

export type AuthResponse = { user: UserOut; session: Session | null };

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

  me: (token: string) => request<UserOut>("/v1/auth/me", { token }),
};
