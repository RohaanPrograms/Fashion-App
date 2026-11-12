// "Save your wardrobe": turns this guest into a normal account WITHOUT
// changing its id, so every like and set is kept. It's also how anyone makes
// an account ("Sign up" on the login screen starts a guest and comes here).
//   1. email           -> the server asks Supabase to email a one-time code
//   2. code + password -> the code confirms the address (the account stops
//                         being a guest), then the password is set at once
// Code and password are on the SAME screen so nobody can leave between them
// and end up with a confirmed account that has no password. If the password
// is refused (say, too weak), only the password box stays: the email is
// already confirmed by then.
import { Link, useRouter } from "expo-router";
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

// "password" is only reached if the code worked but the password was refused.
type Stage = "email" | "confirm" | "password";

const COPY: Record<Stage, { title: string; button: string }> = {
  email: { title: "Save your wardrobe", button: "Send code" },
  confirm: { title: "Check your email", button: "Save" },
  password: { title: "Choose another password", button: "Save" },
};

// Supabase's code length is a project setting (8 digits on ours); the server
// accepts 6 to 10, so the field does too.
const CODE_PATTERN = /^\d{6,10}$/;
const MIN_PASSWORD = 8;

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
      : stage === "confirm"
        ? CODE_PATTERN.test(code) && password.length >= MIN_PASSWORD
        : password.length >= MIN_PASSWORD;
  const ready = filledIn && !busy;

  function submit() {
    if (stage === "email") {
      void run(async () => {
        await startUpgrade(email.trim());
        setStage("confirm");
      });
    } else if (stage === "confirm") {
      void run(async () => {
        await confirmUpgrade(email.trim(), code);
        // The account is confirmed now. If the password is refused below,
        // the screen stays on just the password box.
        setStage("password");
        await setPassword(password);
        router.replace("/");
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
      : stage === "confirm"
        ? `Type the code we sent to ${email.trim()}, and choose a password so you can log in anywhere.`
        : "Your email is confirmed, but that password was refused. Try a longer or less common one.";

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
        {stage === "confirm" && (
          <>
            <Text style={styles.label}>Code</Text>
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
          </>
        )}
        {(stage === "confirm" || stage === "password") && (
          <>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPasswordText}
              placeholder={`At least ${MIN_PASSWORD} characters`}
              placeholderTextColor={colors.muted}
              secureTextEntry
            />
          </>
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

        {stage === "email" && (
          // For a guest who already has an account (say, from another device).
          // The login screen warns that this guest's likes stay behind.
          <View style={styles.linkRow}>
            <Text style={styles.linkText}>Already have an account? </Text>
            <Link href="/login" style={styles.link}>
              Log in
            </Link>
          </View>
        )}

        {stage === "confirm" && (
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
