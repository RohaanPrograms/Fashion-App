// Temporary landing screen until the tabs arrive: proves the guest flow works.
import { Text, View } from "react-native";

import { useAuth } from "../src/auth/AuthContext";
import { AccountBanner } from "../src/components/AccountBanner";
import { styles } from "../src/theme";

export default function Home() {
  const { user } = useAuth();
  return (
    <View style={styles.screen}>
      <Text style={styles.title}>You're in</Text>
      <Text style={styles.subtitle}>Account {user?.id}</Text>
      <AccountBanner />
    </View>
  );
}
