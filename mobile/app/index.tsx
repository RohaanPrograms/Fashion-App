// The first screen. While AuthContext finds or creates a session it shows a
// spinner; then it sends the visitor on:
//   signed in (guest or not)  -> the app
//   couldn't start a session  -> the reason, with "Try again" and "Log in"
//   signed out on purpose     -> the login screen
import { Link, Redirect } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { useAuth } from "../src/auth/AuthContext";
import { styles } from "../src/theme";

export default function Index() {
  const { user, loading, startupError, restoreOrStartGuest } = useAuth();

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
        <Text style={[styles.info, { marginTop: 16 }]}>Getting your feed ready…</Text>
      </View>
    );
  }
  if (user) return <Redirect href="/feed" />;
  if (startupError) {
    return (
      <View style={styles.screen}>
        <Text style={styles.title}>Couldn't start</Text>
        <Text style={styles.subtitle}>{startupError}</Text>
        <Pressable style={styles.button} onPress={restoreOrStartGuest}>
          <Text style={styles.buttonText}>Try again</Text>
        </Pressable>
        <View style={styles.linkRow}>
          <Text style={styles.linkText}>Have an account? </Text>
          <Link href="/login" style={styles.link}>
            Log in
          </Link>
        </View>
      </View>
    );
  }
  return <Redirect href="/login" />;
}
