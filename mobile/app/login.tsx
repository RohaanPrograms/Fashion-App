// Login screen: email + password -> calls the backend, stores the token.
// Optional: a visitor is never sent here on a first visit (they start as a
// guest). It's reached after logging out, or from "Couldn't start".
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native";

import { useAuth } from "../src/auth/AuthContext";
import { colors, styles } from "../src/theme";

export default function Login() {
  const { signIn, user, continueAsGuest } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = email.trim().length > 0 && password.length > 0 && !submitting;

  async function onSubmit() {
    setError(null);
    setSubmitting(true);
    try {
      await signIn(email.trim(), password);
      router.replace("/"); // the first screen sends a signed-in user into the app
    } catch (e: any) {
      setError(e?.detail ?? "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.screen}>
        <Text style={styles.title}>Welcome back</Text>
        <Text style={styles.subtitle}>Log in to continue.</Text>
        {user?.is_anonymous && (
          <Text style={styles.info}>
            Logging in switches to that account. This guest's likes stay with the
            guest; to keep them, save your wardrobe with an email instead.
          </Text>
        )}

        <Text style={styles.label}>Email</Text>
        <TextInput
          style={styles.input}
          value={email}
          onChangeText={setEmail}
          placeholder="you@example.com"
          placeholderTextColor={colors.muted}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          inputMode="email"
        />

        <Text style={styles.label}>Password</Text>
        <TextInput
          style={styles.input}
          value={password}
          onChangeText={setPassword}
          placeholder="Your password"
          placeholderTextColor={colors.muted}
          secureTextEntry
        />

        {error && <Text style={styles.error}>{error}</Text>}

        <Pressable
          style={[styles.button, !canSubmit && styles.buttonDisabled]}
          onPress={onSubmit}
          disabled={!canSubmit}
        >
          {submitting ? (
            <ActivityIndicator color={colors.primaryText} />
          ) : (
            <Text style={styles.buttonText}>Log in</Text>
          )}
        </Pressable>

        {(!user || user.is_anonymous) && (
          // There is one way to make an account: start as a guest (if not one
          // already) and "save your wardrobe" with an emailed code + password.
          // Anything liked before saving is kept.
          <View style={styles.linkRow}>
            <Text style={styles.linkText}>Don't have an account? </Text>
            <Pressable
              accessibilityRole="link"
              onPress={async () => {
                if (!user) await continueAsGuest();
                router.push("/save");
              }}
            >
              <Text style={styles.link}>Sign up</Text>
            </Pressable>
          </View>
        )}

        {!user && (
          <Pressable
            style={styles.linkRow}
            onPress={async () => {
              await continueAsGuest();
              router.replace("/");
            }}
          >
            <Text style={styles.link}>Continue as a guest</Text>
          </Pressable>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}
