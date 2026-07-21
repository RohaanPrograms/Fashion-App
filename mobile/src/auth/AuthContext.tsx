// Holds the "who is logged in" state for the whole app.
//
// React Context is a way to share one piece of state with every screen without
// passing it down manually through props. Any screen can call `useAuth()` to
// read the current user or trigger sign in / sign up / sign out.
//
// ---------------------------------------------------------------------------
// Staying logged in past the first hour
// ---------------------------------------------------------------------------
// Supabase hands out two tokens. The ACCESS token is sent on every request to
// prove who you are, and it expires after about an hour on purpose — a stolen
// one is only briefly useful. The REFRESH token is long-lived and does exactly
// one job: trade itself in for a new access token.
//
// So instead of asking "is the user logged in?" we ask "do we have a usable
// access token right now?" — and if it's about to expire, we quietly swap it
// for a fresh one before the request goes out. The user never notices.
//
// Screens should never read the access token directly. Call `getValidToken()`,
// which always returns one that is good to use.

import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AppState } from "react-native";

import {
  api,
  toStoredSession,
  type ApiError,
  type StoredSession,
  type UserOut,
} from "../api/client";

// Where the saved session lives on the device.
const SESSION_KEY = "auth_session";
// The old key, which stored a bare access token with no refresh token. Anyone
// who used a build from before refresh existed still has one lying around.
const LEGACY_TOKEN_KEY = "access_token";

// Refresh this long before the token actually expires. Without a margin, a
// token could pass the "still valid" check and then die while the request is
// in flight over a slow connection.
const REFRESH_MARGIN_MS = 60_000;

type AuthContextValue = {
  user: UserOut | null;
  // true while we check the device for a saved session at startup
  loading: boolean;
  signUp: (email: string, password: string) => Promise<{ needsEmailConfirm: boolean }>;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** An access token guaranteed to still be valid — refreshing first if needed. */
  getValidToken: () => Promise<string>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// A network failure (no wifi, backend down) is not the same as a rejected
// token. The first should leave the user signed in to retry later; only the
// second means the session is genuinely dead.
function isNetworkError(err: unknown): boolean {
  return (err as ApiError)?.status === 0;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  // The session lives in a ref, not state, because async code below needs to
  // read the CURRENT value. A state variable captured inside an async function
  // is frozen at the value it had when that function started.
  const sessionRef = useRef<StoredSession | null>(null);

  // If three screens all ask for a token at the same moment on a stale
  // session, we want one refresh call, not three. Everyone waits on the same
  // in-flight promise.
  const refreshInFlight = useRef<Promise<StoredSession> | null>(null);

  async function storeSession(session: StoredSession) {
    sessionRef.current = session;
    await AsyncStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }

  async function clearSession() {
    sessionRef.current = null;
    refreshInFlight.current = null;
    setUser(null);
    await AsyncStorage.multiRemove([SESSION_KEY, LEGACY_TOKEN_KEY]);
  }

  function refreshSession(): Promise<StoredSession> {
    if (refreshInFlight.current) return refreshInFlight.current;

    const pending = (async () => {
      const current = sessionRef.current;
      if (!current) throw { status: 401, detail: "Not signed in." } as ApiError;

      try {
        const res = await api.refresh(current.refresh_token);
        const next = toStoredSession(res);
        if (!next) {
          throw { status: 401, detail: "Refresh returned no session." } as ApiError;
        }
        await storeSession(next);
        return next;
      } catch (err) {
        // Backend rejected the refresh token (expired, or signed out
        // elsewhere) — the session is really over. A network blip is not,
        // so leave that session intact and let the caller retry.
        if (!isNetworkError(err)) await clearSession();
        throw err;
      } finally {
        refreshInFlight.current = null;
      }
    })();

    refreshInFlight.current = pending;
    return pending;
  }

  async function getValidToken(): Promise<string> {
    const current = sessionRef.current;
    if (!current) throw { status: 401, detail: "Not signed in." } as ApiError;

    if (Date.now() < current.expires_at - REFRESH_MARGIN_MS) {
      return current.access_token;
    }
    const refreshed = await refreshSession();
    return refreshed.access_token;
  }

  // On app startup: look for a saved session, renew it if the access token
  // went stale while the app was closed, and log the user straight back in.
  useEffect(() => {
    (async () => {
      try {
        // Builds from before refresh existed saved a bare access token. There
        // is no refresh token to rescue it with, so drop it and require a
        // fresh login once.
        await AsyncStorage.removeItem(LEGACY_TOKEN_KEY);

        const raw = await AsyncStorage.getItem(SESSION_KEY);
        if (raw) {
          sessionRef.current = JSON.parse(raw) as StoredSession;
          const token = await getValidToken(); // refreshes if it expired
          setUser(await api.me(token));
        }
      } catch {
        await clearSession(); // unreadable or rejected — start clean
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Coming back to a backgrounded app is the moment a token is most likely to
  // have expired. Renew it now so the first screen the user taps doesn't stall.
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state !== "active") return;
      const current = sessionRef.current;
      if (!current) return;
      if (Date.now() >= current.expires_at - REFRESH_MARGIN_MS) {
        // Failures are already handled inside refreshSession (it signs the
        // user out on a rejected token); nothing to do here but not crash.
        refreshSession().catch(() => {});
      }
    });
    return () => subscription.remove();
  }, []);

  async function adoptSession(session: StoredSession) {
    await storeSession(session);
    setUser(await api.me(session.access_token));
  }

  async function signUp(email: string, password: string) {
    const res = await api.signup(email, password);
    const session = toStoredSession(res);
    // If Supabase has "confirm email" turned on, no session is returned yet —
    // the user must click a link in their email before they can log in.
    if (!session) return { needsEmailConfirm: true };
    await adoptSession(session);
    return { needsEmailConfirm: false };
  }

  async function signIn(email: string, password: string) {
    const res = await api.login(email, password);
    const session = toStoredSession(res);
    if (!session) {
      throw { status: 400, detail: "Login did not return a session." } as ApiError;
    }
    await adoptSession(session);
  }

  async function signOut() {
    await clearSession();
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, signUp, signIn, signOut, getValidToken }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// Convenience hook so screens can just call `useAuth()`.
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
