// The very first screen. It shows a spinner while AuthContext checks the device
// for a saved session; the root layout then redirects to /login or /home.
import { ActivityIndicator, View } from "react-native";

import { styles } from "../src/theme";

export default function Index() {
  return (
    <View style={styles.centered}>
      <ActivityIndicator size="large" />
    </View>
  );
}
