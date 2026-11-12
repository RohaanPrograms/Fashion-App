// Who you are, and what you can do about it. Guests see the offer to keep
// their wardrobe; signed-in users see their email and a log-out link.
// Guests get no "log out": it would abandon their account for good.
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "../auth/AuthContext";
import { colors } from "../theme";

export function AccountBanner() {
  const { user, signOut } = useAuth();
  const router = useRouter();
  if (!user) return null;

  if (user.is_anonymous) {
    return (
      <View style={local.box}>
        <Text style={local.text}>
          You're browsing as a guest. Your likes are kept on this device only.
        </Text>
        <Pressable onPress={() => router.push("/save")} accessibilityRole="link">
          <Text style={local.action}>Save your wardrobe with an email →</Text>
        </Pressable>
      </View>
    );
  }
  return (
    <View style={local.box}>
      <Text style={local.text}>Signed in as {user.email}</Text>
      <Pressable onPress={signOut} accessibilityRole="button">
        <Text style={local.action}>Log out</Text>
      </Pressable>
    </View>
  );
}

const local = StyleSheet.create({
  box: {
    backgroundColor: colors.fieldBg,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    gap: 6,
  },
  text: { color: colors.muted, fontSize: 14 },
  action: { color: colors.primary, fontSize: 14, fontWeight: "600" },
});
