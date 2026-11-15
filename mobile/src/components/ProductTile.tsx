// A small photo tile: photo, name, then type · price. Tappable when onPress
// is given; `selected` draws a dark outline (the set builder will use that).
import { Image } from "expo-image";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { Product } from "../api/client";
import { usePriceFormatter } from "../currencyStore";
import { colors } from "../theme";

type Props = { product: Product; width: number; selected?: boolean; onPress?: () => void };

export function ProductTile({ product, width, selected = false, onPress }: Props) {
  const price = usePriceFormatter();
  const meta = [product.type, price(product.price, product.currency)].filter(Boolean).join(" · ");
  const body = (
    <View style={{ width }}>
      <View style={[t.photoBox, selected && t.selected]}>
        {/* A ternary, not `&&`: an empty-string URL would render "" outside <Text>, which crashes on phones. */}
        {product.image_url ? (
          <Image
            source={product.image_url}
            style={t.photo}
            contentFit="cover"
            transition={150}
            accessibilityLabel={product.name}
          />
        ) : null}
      </View>
      <Text style={t.name} numberOfLines={1}>{product.name}</Text>
      <Text style={t.meta} numberOfLines={1}>{meta}</Text>
    </View>
  );
  if (!onPress) return body;
  return (
    // aria-selected as well as accessibilityState: on the web, only the former
    // reaches the page, so a screen reader can say which tiles are picked.
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityState={{ selected }} aria-selected={selected}>
      {body}
    </Pressable>
  );
}

const t = StyleSheet.create({
  // 2:3, the photos' own shape (400 x 600), so "cover" fills the tile
  // without cutting off the top or bottom of the garment.
  photoBox: {
    aspectRatio: 2 / 3,
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: colors.fieldBg,
    borderWidth: 2,
    borderColor: "transparent",
  },
  selected: { borderColor: colors.primary },
  photo: { width: "100%", height: "100%" },
  name: { fontSize: 13, color: colors.text, marginTop: 6 },
  meta: { fontSize: 13, color: colors.muted },
});
