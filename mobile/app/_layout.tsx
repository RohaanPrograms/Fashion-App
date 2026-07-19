// The root layout wraps every screen in the app.
//
// In Expo Router, the file layout inside app/ IS the navigation:
//   app/index.tsx  -> "/"        (a loading splash while we check login state)
//   app/login.tsx  -> "/login"
//   app/signup.tsx -> "/signup"
//   app/home.tsx   -> "/home"    (only reachable when logged in)
//
// This file also enforces the rule "you must be logged in to see /home" by
// redirecting based on the auth state from AuthContext.

import { Stack, useRouter, useSegments } from "expo-router";
import { useEffect } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AuthProvider, useAuth } from "../src/auth/AuthContext";

function RootNavigator() {
  const { user, loading } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (loading) return; // wait until we know whether a session exists

    const onAuthScreen = segments[0] === "login" || segments[0] === "signup";

    if (!user && !onAuthScreen) {
      // Not logged in and trying to view a protected screen -> go to login.
      router.replace("/login");
    } else if (user && onAuthScreen) {
      // Already logged in but sitting on login/signup -> go to home.
      router.replace("/home");
    }
  }, [user, loading, segments]);

  return <Stack screenOptions={{ headerShown: false }} />;
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <RootNavigator />
      </AuthProvider>
    </SafeAreaProvider>
  );
}
