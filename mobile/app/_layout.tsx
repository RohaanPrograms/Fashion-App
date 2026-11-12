// The root layout wraps every screen in the app.
//
// In Expo Router, the file layout inside app/ IS the navigation. This file
// also decides which screens need a signed-in user, with Stack.Protected:
// screens inside it can only be reached while `guard` is true. Anyone on one
// when it turns false (say, after logging out) is sent back to "/" (index.tsx),
// which works out where they should be.
//
// Guests count as signed in: they have a real (email-less) account.
//
// While the saved session is still being checked (`loading`), the gate stays
// OPEN. Otherwise a reload on /wardrobe would see "no user yet", be sent to
// "/", and land on the feed. The tab layout shows a spinner during that check
// so no screen loads data before we know who the visitor is.

import { Stack } from "expo-router";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AuthProvider, useAuth } from "../src/auth/AuthContext";

function RootNavigator() {
  const { user, loading } = useAuth();

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="login" />
      <Stack.Protected guard={loading || !!user}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="save" />
      </Stack.Protected>
    </Stack>
  );
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
