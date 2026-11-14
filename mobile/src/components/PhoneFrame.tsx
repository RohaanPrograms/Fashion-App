// People open links on laptops, and a full-width swipe app on a big monitor
// looks broken (a tab bar stretched across the screen, buttons far apart).
// On a wide browser window this shows the whole app at phone width, centred
// on a plain background. On phones, and narrow windows, it does nothing.
import type { ReactNode } from "react";
import { Platform, StyleSheet, View, useWindowDimensions } from "react-native";

const PHONE_WIDTH = 430;

export function PhoneFrame({ children }: { children: ReactNode }) {
  const { width } = useWindowDimensions();
  if (Platform.OS !== "web" || width <= PHONE_WIDTH) return <>{children}</>;
  return (
    <View style={s.backdrop}>
      <View style={s.phone}>{children}</View>
    </View>
  );
}

const s = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "#f3f4f6", alignItems: "center" },
  phone: {
    flex: 1,
    width: PHONE_WIDTH,
    backgroundColor: "#ffffff",
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderColor: "#e5e7eb",
    overflow: "hidden",
  },
});
