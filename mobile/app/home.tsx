// Home screen: the first screen a logged-in user sees.
// For Phase 0 this is a placeholder that proves auth works end to end.
import { Pressable, Text, View } from "react-native";

import { useAuth } from "../src/auth/AuthContext";
import { colors, styles } from "../src/theme";

export default function Home() {
  const { user, signOut } = useAuth();

  return (
    <View style={styles.screen}>
      <Text style={styles.title}>You're in 🎉</Text>
      <Text style={styles.subtitle}>
        Logged in as {user?.email ?? user?.id}
      </Text>

      <Pressable style={styles.button} onPress={signOut}>
        <Text style={styles.buttonText}>Log out</Text>
      </Pressable>
    </View>
  );
}
