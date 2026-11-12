// The bottom tab bar: the whole app is these three tabs.
//   Feed      swipe cards; every like lands in the wardrobe
//   Wardrobe  everything you liked
//   Sets      outfits built from the wardrobe
//
// The folder name in brackets, (tabs), is a "group": it organises files
// without adding to the web address, so app/(tabs)/feed.tsx is just /feed.
import Ionicons from "@expo/vector-icons/Ionicons";
import { Tabs } from "expo-router";
import { ActivityIndicator, Text, View } from "react-native";

import { useAuth } from "../../src/auth/AuthContext";
import { colors, styles } from "../../src/theme";

export default function TabLayout() {
  const { loading } = useAuth();

  // On a reload the tabs open before the saved session has been checked (the
  // root gate lets them, so the address isn't lost). Wait here until we know
  // who the visitor is, so no tab asks the server for data too early.
  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
        <Text style={[styles.info, { marginTop: 16 }]}>Getting your feed ready…</Text>
      </View>
    );
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.muted,
      }}
    >
      <Tabs.Screen
        name="feed"
        options={{
          title: "Feed",
          tabBarIcon: ({ color, size }) => <Ionicons name="flame-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="wardrobe"
        options={{
          title: "Wardrobe",
          tabBarIcon: ({ color, size }) => <Ionicons name="shirt-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="outfits"
        options={{
          // The file matches the server's /v1/outfits; visitors see "Sets".
          title: "Sets",
          tabBarIcon: ({ color, size }) => <Ionicons name="layers-outline" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
