// The ⓘ panel, drawn over the bottom of the card's photo: what the garment
// is, then why the model put it in your feed.
import { ScrollView, StyleSheet, Text, View } from "react-native";

import type { Product, Reason } from "../api/client";
import { aboutPiece, explainReason } from "../feed/reason";

type Props = { product: Product; reason: Reason; likesNeeded: number };

export function WhyPanel({ product, reason, likesNeeded }: Props) {
  const about = aboutPiece(product);
  const why = explainReason(reason, likesNeeded);
  return (
    <View style={s.panel} accessibilityLiveRegion="polite">
      {/* Scrolls if a long description doesn't fit over a short photo. */}
      <ScrollView contentContainerStyle={s.content}>
        <Text style={s.label}>ABOUT THIS PIECE</Text>
        {about.facts !== "" && <Text style={s.headline}>{about.facts}</Text>}
        {about.description && <Text style={s.detail}>{about.description}</Text>}

        <View style={s.divider} />

        <Text style={s.label}>WHY YOU'RE SEEING THIS</Text>
        <Text style={s.headline}>{why.headline}</Text>
        <Text style={s.detail}>{why.detail}</Text>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  panel: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 12,
    maxHeight: "85%",
    backgroundColor: "rgba(17, 17, 17, 0.88)",
    borderRadius: 12,
  },
  content: { padding: 14, gap: 6 },
  label: { color: "#9ca3af", fontSize: 11, fontWeight: "700", letterSpacing: 0.8 },
  headline: { color: "#ffffff", fontSize: 16, fontWeight: "700" },
  detail: { color: "#e5e7eb", fontSize: 14, lineHeight: 20 },
  divider: { height: 1, backgroundColor: "rgba(255, 255, 255, 0.2)", marginVertical: 6 },
});
