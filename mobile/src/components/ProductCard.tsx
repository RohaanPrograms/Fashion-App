// One swipe card: photo, name, brand, price, and the buttons beneath.
//
// Deliberately "presentational": it only draws what it's given and reports
// taps through onLike / onDislike. It knows nothing about the network,
// batches or gestures. A swipe gesture can be added later by wrapping this
// component and calling the same callbacks, with no rewrite.
import { Image } from "expo-image";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { Product } from "../api/client";
import { formatPrice } from "../format";
import { colors } from "../theme";

type Props = {
  product: Product;
  onLike: () => void;
  onDislike: () => void;
};

export function ProductCard({ product, onLike, onDislike }: Props) {
  const meta = [product.brand, formatPrice(product.price, product.currency)].filter(Boolean).join(" · ");
  return (
    <View style={card.wrap}>
      <View style={card.photoBox}>
        {product.image_url ? (
          <Image
            source={product.image_url}
            style={card.photo}
            contentFit="contain"
            transition={200}
            accessibilityLabel={product.name}
          />
        ) : (
          <View style={[card.photo, card.noPhoto]}>
            <Text style={card.muted}>No photo</Text>
          </View>
        )}
      </View>
      <Text style={card.name} numberOfLines={2}>{product.name}</Text>
      <Text style={card.meta}>{meta}</Text>
      <View style={card.buttons}>
        <RoundButton label="✕" hint="Dislike" onPress={onDislike} />
        <RoundButton label="♡" hint="Like" onPress={onLike} />
      </View>
    </View>
  );
}

export function RoundButton({ label, hint, onPress }: { label: string; hint: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={hint}
      style={({ pressed }) => [card.round, pressed && card.pressed]}
    >
      <Text style={card.roundText}>{label}</Text>
    </Pressable>
  );
}

// The photos are 400 x 600. Capping the card near that width keeps them
// sharp on a desktop (a 1,500 px-wide card blew them up about 4x), and
// "contain" shows the whole garment instead of cropping it to fit the box.
const MAX_CARD_WIDTH = 420;

const card = StyleSheet.create({
  wrap: { flex: 1, width: "100%", maxWidth: MAX_CARD_WIDTH },
  // The grey box doubles as the placeholder while the photo loads.
  photoBox: { flex: 1, borderRadius: 16, overflow: "hidden", backgroundColor: colors.fieldBg },
  photo: { width: "100%", height: "100%" },
  noPhoto: { alignItems: "center", justifyContent: "center" },
  muted: { color: colors.muted },
  name: { fontSize: 18, fontWeight: "600", color: colors.text, marginTop: 12 },
  meta: { fontSize: 15, color: colors.muted, marginTop: 2 },
  buttons: { flexDirection: "row", justifyContent: "center", gap: 32, marginTop: 16 },
  round: {
    width: 64,
    height: 64,
    borderRadius: 32,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
  pressed: { opacity: 0.6 },
  roundText: { fontSize: 26, color: colors.text },
});
