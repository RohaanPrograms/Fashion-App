// The swipe feed. The cards arrive in a later task.
import { Text, View } from "react-native";

import { styles } from "../../src/theme";

export default function Feed() {
  return (
    <View style={styles.centered}>
      <Text style={styles.subtitle}>The feed goes here.</Text>
    </View>
  );
}
