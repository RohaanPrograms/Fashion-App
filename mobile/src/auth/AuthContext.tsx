// Holds the "who is signed in" state for the whole app.
//
// React Context is a way to share one piece of state with every screen without
// passing it down manually through props. Any screen can call `useAuth()`.
//
// ---------------------------------------------------------------------------
// Guest first
// ---------------------------------------------------------------------------
// A visitor never meets a signup wall. On startup the app reuses the session
// saved on this device or, if there is none, quietly creates a GUEST: a real
// account with no email. The decision lives in startup.ts as a pure, tested
// function; this file only supplies the real storage and network calls.
//
// A guest can "save their wardrobe": confirm an email with an emailed code,
// then set a password, on the SAME account, so every like and set is kept.
//
// ---------------------------------------------------------------------------
// Staying signed in past the first hour
// ---------------------------------------------------------------------------
// Supabase hands out two tokens. The ACCESS token is sent on every request to
// prove who you are, and it expires after about an hour on purpose — a stolen
// one is only briefly useful. The REFRESH token is long-lived and does exactly
// one job: trade itself in for a new access token.
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
import { isNetworkError, needsRefresh, startSession, startupMessage } from "./startup";

// Where the saved session lives on the device.
const SESSION_KEY = "auth_session";
// The old key, which stored a bare access token with no refresh token.
const LEGACY_TOKEN_KEY = "access_token";

type AuthContextValue = {
  user: UserOut | null;
  // true while the app is finding or creating a session
  loading: boolean;
  /** Why the app couldn't start a session (offline, guest limit…), or null. */
  startupError: string | null;
  /** Reuse the saved session, or start a new guest. Also "Try again". */
  restoreOrStartGuest: () => Promise<void>;
  signUp: (email: string, password: string) => Promise<{ needsEmailConfirm: boolean }>;
  signIn: (email: string, password: string) => Promise<void>;
  /** Save your wardrobe, step 1: email a code to this address. */
  startUpgrade: (email: string) => Promise<void>;
  /** Step 2: the code makes this guest a normal account (same id, everything kept). */
  confirmUpgrade: (email: string, code: string) => Promise<void>;
  /** Step 3, retry-able on its own: set the verified account's password. */
  setPassword: (password: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** An access token guaranteed to still be valid — refreshing first if needed. */
  getValidToken: () => Promise<string>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [startupError, setStartupError] = useState<string | null>(null);

  // The session lives in a ref, not state, because async code below needs to
  // read the CURRENT value. A state variable captured inside an async function
  // is frozen at the value it had when that function started.
  const sessionRef = useRef<StoredSession | null>(null);

  // If three screens all ask for a token at the same moment on a stale
  // session, we want one refresh call, not three.
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
        // Backend rejected the refresh token: the session is really over.
        // A network blip is not, so leave that session intact.
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
    if (!needsRefresh(current, Date.now())) return current.access_token;
    const refreshed = await refreshSession();
    return refreshed.access_token;
  }

  async function restoreOrStartGuest() {
    setLoading(true);
    setStartupError(null);
    try {
      await AsyncStorage.removeItem(LEGACY_TOKEN_KEY);
      const result = await startSession({
        now: Date.now,
        loadSaved: async () => {
          const raw = await AsyncStorage.getItem(SESSION_KEY);
          return raw ? (JSON.parse(raw) as StoredSession) : null;
        },
        save: storeSession,
        clear: clearSession,
        refresh: api.refresh,
        me: api.me,
        createGuest: api.anonymous,
      });
      if (result.kind === "ready") {
        sessionRef.current = result.session;
        setUser(result.user);
      } else {
        setStartupError(startupMessage(result.error));
      }
    } catch {
      setStartupError("Something went wrong starting the app. Try again.");
    } finally {
      setLoading(false);
    }
  }

  // On app startup: reuse this device's session, or start a guest.
  useEffect(() => {
    void restoreOrStartGuest();
  }, []);

  // Coming back to a backgrounded app is the moment a token is most likely to
  // have expired. Renew it now so the first screen the user taps doesn't stall.
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state !== "active") return;
      const current = sessionRef.current;
      if (current && needsRefresh(current, Date.now())) {
        // Failures are handled inside refreshSession; just don't crash.
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
    // If Supabase has "confirm email" turned on, no session is returned yet.
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

  async function startUpgrade(email: string) {
    await api.upgradeStart(await getValidToken(), email);
  }

  async function confirmUpgrade(email: string, code: string) {
    const res = await api.upgradeVerify(await getValidToken(), email, code);
    const session = toStoredSession(res);
    if (!session) {
      throw { status: 503, detail: "Confirming the code returned no session." } as ApiError;
    }
    // A fresh token that no longer says "guest". Same account id.
    await storeSession(session);
    setUser(res.user);
  }

  async function setPassword(password: string) {
    await api.setPassword(await getValidToken(), password);
  }

  async function signOut() {
    await clearSession();
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        startupError,
        restoreOrStartGuest,
        signUp,
        signIn,
        startUpgrade,
        confirmUpgrade,
        setPassword,
        signOut,
        getValidToken,
      }}
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
