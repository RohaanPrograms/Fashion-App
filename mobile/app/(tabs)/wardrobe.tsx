// Everything you liked. The grid arrives in a later task.
// The account banner lives here: "Save your wardrobe with an email" for
// guests, the email and "Log out" for everyone else.
import { Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AccountBanner } from "../../src/components/AccountBanner";
import { styles } from "../../src/theme";

export default function Wardrobe() {
  return (
    <SafeAreaView style={[styles.screen, { justifyContent: "flex-start", paddingTop: 16 }]}>
      <Text style={styles.title}>Wardrobe</Text>
      <AccountBanner />
      <View style={{ marginTop: 24 }}>
        <Text style={styles.subtitle}>Your liked items will appear here.</Text>
      </View>
    </SafeAreaView>
  );
}
