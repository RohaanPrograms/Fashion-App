// "Save your wardrobe": turns this guest into a normal account WITHOUT
// changing its id, so every like and set is kept.
//   1. email    -> the server asks Supabase to email a one-time code
//   2. code     -> confirms the address; the account stops being a guest
//   3. password -> so the account can log in on another device
// If the password step fails, only that step is retried: the email is
// already confirmed by then.
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

import type { ApiError } from "../src/api/client";
import { useAuth } from "../src/auth/AuthContext";
import { colors, styles } from "../src/theme";

type Stage = "email" | "code" | "password";

const COPY: Record<Stage, { title: string; button: string }> = {
  email: { title: "Save your wardrobe", button: "Send code" },
  code: { title: "Check your email", button: "Confirm" },
  password: { title: "Choose a password", button: "Save" },
};

// Supabase's code length is a project setting (8 digits on ours); the server
// accepts 6 to 10, so the field does too.
const CODE_PATTERN = /^\d{6,10}$/;

export default function Save() {
  const { startUpgrade, confirmUpgrade, setPassword } = useAuth();
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPasswordText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(step: () => Promise<void>) {
    setError(null);
    setBusy(true);
    try {
      await step();
    } catch (e) {
      setError((e as ApiError)?.detail ?? "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const filledIn =
    stage === "email"
      ? email.trim().length > 0
      : stage === "code"
        ? CODE_PATTERN.test(code)
        : password.length >= 8;
  const ready = filledIn && !busy;

  function submit() {
    if (stage === "email") {
      void run(async () => {
        await startUpgrade(email.trim());
        setStage("code");
      });
    } else if (stage === "code") {
      void run(async () => {
        await confirmUpgrade(email.trim(), code);
        setStage("password");
      });
    } else {
      void run(async () => {
        await setPassword(password);
        router.replace("/");
      });
    }
  }

  const hint =
    stage === "email"
      ? "We'll email you a code. Nothing you've swiped is lost."
      : stage === "code"
        ? `Type the code we sent to ${email.trim()}.`
        : "Your email is confirmed. Add a password so you can log in anywhere.";

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.screen}>
        <Text style={styles.title}>{COPY[stage].title}</Text>
        <Text style={styles.subtitle}>{hint}</Text>

        {stage === "email" && (
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
        )}
        {stage === "code" && (
          <TextInput
            style={styles.input}
            value={code}
            onChangeText={(text) => setCode(text.replace(/\D/g, ""))}
            placeholder="12345678"
            placeholderTextColor={colors.muted}
            keyboardType="number-pad"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={10}
          />
        )}
        {stage === "password" && (
          <TextInput
            style={styles.input}
            value={password}
            onChangeText={setPasswordText}
            placeholder="At least 8 characters"
            placeholderTextColor={colors.muted}
            secureTextEntry
          />
        )}

        {error && <Text style={styles.error}>{error}</Text>}

        <Pressable
          style={[styles.button, !ready && styles.buttonDisabled]}
          onPress={submit}
          disabled={!ready}
        >
          {busy ? (
            <ActivityIndicator color={colors.primaryText} />
          ) : (
            <Text style={styles.buttonText}>{COPY[stage].button}</Text>
          )}
        </Pressable>

        {stage === "code" && (
          <Pressable
            style={styles.linkRow}
            onPress={() => {
              setCode("");
              setStage("email");
            }}
          >
            <Text style={styles.link}>Use a different email, or send a new code</Text>
          </Pressable>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}
