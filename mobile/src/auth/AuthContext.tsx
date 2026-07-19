// Holds the "who is logged in" state for the whole app.
//
// React Context is a way to share one piece of state with every screen without
// passing it down manually through props. Any screen can call `useAuth()` to
// read the current user or trigger sign in / sign up / sign out.

import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { api, type UserOut } from "../api/client";

// The key we store the login token under on the device.
const TOKEN_KEY = "access_token";

type AuthContextValue = {
  user: UserOut | null;
  token: string | null;
  // true while we check the device for a saved session at startup
  loading: boolean;
  signUp: (email: string, password: string) => Promise<{ needsEmailConfirm: boolean }>;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // On app startup: look for a token saved from a previous session and, if the
  // backend still accepts it, log the user straight back in.
  useEffect(() => {
    (async () => {
      try {
        const saved = await AsyncStorage.getItem(TOKEN_KEY);
        if (saved) {
          const me = await api.me(saved); // throws if the token expired
          setToken(saved);
          setUser(me);
        }
      } catch {
        await AsyncStorage.removeItem(TOKEN_KEY); // stale/invalid token — clear it
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Save the token on the device and load the matching user.
  async function persistSession(accessToken: string) {
    await AsyncStorage.setItem(TOKEN_KEY, accessToken);
    const me = await api.me(accessToken);
    setToken(accessToken);
    setUser(me);
  }

  async function signUp(email: string, password: string) {
    const res = await api.signup(email, password);
    // If Supabase has "confirm email" turned on, no session is returned yet —
    // the user must click a link in their email before they can log in.
    if (res.session) {
      await persistSession(res.session.access_token);
      return { needsEmailConfirm: false };
    }
    return { needsEmailConfirm: true };
  }

  async function signIn(email: string, password: string) {
    const res = await api.login(email, password);
    if (!res.session) {
      throw { status: 400, detail: "Login did not return a session." };
    }
    await persistSession(res.session.access_token);
  }

  async function signOut() {
    await AsyncStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{ user, token, loading, signUp, signIn, signOut }}
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
