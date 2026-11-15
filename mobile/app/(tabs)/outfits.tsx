// Your saved sets: name, total price, and the pieces head to toe. "+ New set"
// opens the builder; Edit opens the same builder pre-filled
// (src/outfits/BuilderScreen.tsx). Delete asks with a second tap.
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { FlatList, Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api, type ApiError, type Outfit } from "../../src/api/client";
import { useAuth } from "../../src/auth/AuthContext";
import { ConfirmButton } from "../../src/components/ConfirmButton";
import { ProductTile } from "../../src/components/ProductTile";
import { usePriceFormatter } from "../../src/currencyStore";
import { colors, styles } from "../../src/theme";

const MAX_WIDTH = 430; // phone width; a centred column on desktop

export default function Outfits() {
  const { getValidToken } = useAuth();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const price = usePriceFormatter();
  const [outfits, setOutfits] = useState<Outfit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Reload whenever the tab is opened, including on return from the builder.
  const load = useCallback(async () => {
    try {
      const token = await getValidToken();
      setOutfits((await api.outfits(token)).outfits);
      setError(null);
    } catch (err) {
      setError((err as ApiError).detail ?? "Couldn't load your sets.");
    }
  }, []);
  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load])
  );

  // Already confirmed by the button's second tap.
  async function remove(outfit: Outfit) {
    try {
      const token = await getValidToken();
      await api.deleteOutfit(token, outfit.id);
      setOutfits((current) => current?.filter((o) => o.id !== outfit.id) ?? null);
    } catch (err) {
      setError((err as ApiError).detail ?? "Couldn't delete that set.");
    }
  }

  return (
    <SafeAreaView style={s.screen} edges={["top"]}>
      <FlatList
        style={{ width: Math.min(width, MAX_WIDTH), alignSelf: "center" }}
        data={outfits ?? []}
        keyExtractor={(o) => o.id}
        contentContainerStyle={{ padding: 16, gap: 16 }}
        ListHeaderComponent={
          <View style={{ gap: 8 }}>
            <View style={s.headerRow}>
              <Text style={styles.title}>Sets</Text>
              <Pressable onPress={() => router.push("/outfits/new")} accessibilityRole="button" hitSlop={8}>
                <Text style={s.action}>+ New set</Text>
              </Pressable>
            </View>
            {error && <Text style={styles.error}>{error}</Text>}
          </View>
        }
        ListEmptyComponent={
          outfits === null ? null : (
            <Text style={styles.subtitle}>No sets yet. Build one from your wardrobe: 2 or more items, one per row.</Text>
          )
        }
        renderItem={({ item }) => (
          <View style={s.card}>
            <View style={s.headerRow}>
              <Text style={s.name} numberOfLines={1}>{item.name}</Text>
              <Text style={s.total}>
                {item.total_price === null ? "—" : price(item.total_price, item.currency)}
              </Text>
            </View>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10 }}>
              {item.items.map((piece) => (
                <ProductTile key={piece.product.id} product={piece.product} width={90} />
              ))}
            </ScrollView>
            <View style={s.actions}>
              <Pressable
                onPress={() => router.push({ pathname: "/outfits/[id]/edit", params: { id: item.id } })}
                accessibilityRole="button"
                accessibilityLabel={`Edit the set ${item.name}`}
                style={({ pressed }) => [s.edit, pressed && { opacity: 0.6 }]}
              >
                <Text style={s.editText}>Edit</Text>
              </Pressable>
              <View style={{ flex: 1 }}>
                <ConfirmButton
                  label="Delete"
                  confirmLabel="Delete this set?"
                  accessibilityLabel={`Delete the set ${item.name}`}
                  onConfirm={() => void remove(item)}
                />
              </View>
            </View>
          </View>
        )}
      />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  action: { color: colors.primary, fontSize: 15, fontWeight: "600" },
  card: { borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, gap: 10 },
  name: { fontSize: 17, fontWeight: "600", color: colors.text, flexShrink: 1 },
  total: { fontSize: 17, fontWeight: "700", color: colors.text },
  actions: { flexDirection: "row", gap: 10 },
  // Same size as the Delete button beside it, but dark: the everyday action.
  edit: {
    flex: 1,
    borderRadius: 8,
    paddingVertical: 7,
    alignItems: "center",
    backgroundColor: colors.primary,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  editText: { fontSize: 13, color: colors.primaryText, fontWeight: "600" },
});
