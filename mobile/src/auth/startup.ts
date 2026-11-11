// How the app gets a session when it opens: the "guest first" rule.
//
// 1. A session saved on this device is reused (refreshed first if its access
//    token has expired). This is the common case: a returning visitor.
// 2. If there is none, or the server says the saved one is dead, a new guest
//    account is created and saved.
// 3. If the server can't be reached, or is having trouble, NOTHING is thrown
//    away and no guest is created: the screen offers "Try again". Creating a
//    guest on every failed launch would burn through the server's limit of
//    5 new guests per network per hour.
//
// This is a plain function that is handed everything it uses ("deps": storage,
// network calls, the clock). That is called dependency injection: the app
// passes the real ones, the tests pass fakes, so every branch is tested without
// a phone, a browser or a server.

import {
  toStoredSession,
  type ApiError,
  type AuthResponse,
  type StoredSession,
  type UserOut,
} from "../api/client";

// Refresh this long before the token actually expires. Without a margin, a
// token could pass the "still valid" check and then die while the request is
// in flight over a slow connection.
export const REFRESH_MARGIN_MS = 60_000;

export type StartupDeps = {
  now: () => number;
  loadSaved: () => Promise<StoredSession | null>;
  save: (session: StoredSession) => Promise<void>;
  clear: () => Promise<void>;
  refresh: (refreshToken: string) => Promise<AuthResponse>;
  me: (accessToken: string) => Promise<UserOut>;
  createGuest: () => Promise<AuthResponse>;
};

export type StartupResult =
  | { kind: "ready"; session: StoredSession; user: UserOut; isNewGuest: boolean }
  | { kind: "failed"; error: ApiError };

// A network failure (no wifi, server down) is not the same as a rejected
// token. The first should leave the session alone; only the second ends it.
export function isNetworkError(err: unknown): boolean {
  return (err as ApiError)?.status === 0;
}

// Anything thrown that isn't one of our ApiErrors (say, a proxy's HTML error
// page that fails to parse) is treated as server trouble: unknown is not "dead".
function asApiError(err: unknown): ApiError {
  const e = err as Partial<ApiError> | null;
  if (e && typeof e.status === "number" && typeof e.detail === "string") {
    return { status: e.status, detail: e.detail };
  }
  return { status: 500, detail: "Something went wrong." };
}

export function needsRefresh(session: StoredSession, now: number): boolean {
  return now >= session.expires_at - REFRESH_MARGIN_MS;
}

export async function startSession(deps: StartupDeps): Promise<StartupResult> {
  let saved: StoredSession | null = null;
  try {
    saved = await deps.loadSaved();
  } catch {
    await deps.clear(); // unreadable: throw it away and start fresh
  }

  if (saved) {
    try {
      let session = saved;
      if (needsRefresh(session, deps.now())) {
        const next = toStoredSession(await deps.refresh(session.refresh_token));
        if (!next) throw { status: 401, detail: "Refresh returned no session." } as ApiError;
        await deps.save(next);
        session = next;
      }
      const user = await deps.me(session.access_token);
      return { kind: "ready", session, user, isNewGuest: false };
    } catch (err) {
      const error = asApiError(err);
      if (error.status === 0 || error.status >= 500) return { kind: "failed", error };
      await deps.clear(); // the server said this session is over
    }
  }

  try {
    const res = await deps.createGuest();
    const session = toStoredSession(res);
    if (!session) {
      return { kind: "failed", error: { status: 503, detail: "Guest sign-in returned no session." } };
    }
    await deps.save(session);
    return { kind: "ready", session, user: res.user, isNewGuest: true };
  } catch (err) {
    return { kind: "failed", error: asApiError(err) };
  }
}

export function startupMessage(error: ApiError): string {
  if (error.status === 0) {
    return "Can't reach the server. Check your connection and try again.";
  }
  if (error.status === 429) {
    return "Too many new guests from your network in the last hour. Try again later, or log in.";
  }
  return "The server isn't ready right now. Try again in a moment.";
}
