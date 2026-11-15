// Everything you liked, in a grid. Reloads every time the tab is opened, so
// likes from the feed are always there. Remove takes an item out (it still
// counts towards your taste); Start over wipes every swipe. Both ask by
// turning red ("Are you sure?") and act on a second tap: no pop-ups.
// The account banner lives here too: "Save your wardrobe with an email" for
// guests, the email and "Log out" for everyone else. "Filter" narrows the grid
// by category, type, colour and pattern (src/wardrobe/filters.ts).
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { FlatList, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api, type ApiError, type Product } from "../../src/api/client";
import { useAuth } from "../../src/auth/AuthContext";
import { AccountBanner } from "../../src/components/AccountBanner";
import { ConfirmButton } from "../../src/components/ConfirmButton";
import { CurrencyPicker } from "../../src/components/CurrencyPicker";
import { ProductTile } from "../../src/components/ProductTile";
import { WardrobeFilters } from "../../src/components/WardrobeFilters";
import { bumpFeedReset } from "../../src/feed/resetSignal";
import { colors, styles } from "../../src/theme";
import { NO_WARDROBE_FILTER, applyFilter, type WardrobeFilter } from "../../src/wardrobe/filters";

const GAP = 12;
const PADDING = 16;
// Phone width. On a desktop the grid sits in a centred column of this width
// instead of stretching two huge tiles across the window.
const MAX_WIDTH = 430;

export default function Wardrobe() {
  const { getValidToken } = useAuth();
  const { width } = useWindowDimensions();
  const columnWidth = Math.min(width, MAX_WIDTH);
  const tileWidth = (columnWidth - PADDING * 2 - GAP) / 2;

  // null = still loading the first time; [] = loaded, nothing liked yet.
  const [items, setItems] = useState<Product[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Narrows what the grid shows; the title's count stays the whole wardrobe.
  const [filter, setFilter] = useState<WardrobeFilter>(NO_WARDROBE_FILTER);
  const shown = items ? applyFilter(items, filter) : [];

  // useFocusEffect runs every time this tab comes into view. getValidToken
  // always reads the latest session, so the first copy is fine to keep: hence
  // the empty dependency list.
  const load = useCallback(async () => {
    try {
      const token = await getValidToken();
      setItems((await api.wardrobe(token)).items);
      setError(null);
    } catch (err) {
      setError((err as ApiError).detail ?? "Couldn't load your wardrobe.");
    }
  }, []);
  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load])
  );

  // Already confirmed by the button's second tap.
  async function remove(product: Product) {
    try {
      const token = await getValidToken();
      await api.removeFromWardrobe(token, product.id);
      setItems((current) => current?.filter((p) => p.id !== product.id) ?? null);
    } catch (err) {
      setError((err as ApiError).detail ?? "Couldn't remove that item.");
    }
  }

  // Already confirmed by the button's second tap.
  async function startOver() {
    try {
      const token = await getValidToken();
      await api.startOver(token);
      setItems([]);
      bumpFeedReset(); // tells the Feed tab to start again
    } catch (err) {
      setError((err as ApiError).detail ?? "Couldn't start over.");
    }
  }

  return (
    <SafeAreaView style={local.screen} edges={["top"]}>
      <FlatList
        style={{ width: columnWidth, alignSelf: "center" }}
        data={shown}
        keyExtractor={(p) => p.id}
        numColumns={2}
        columnWrapperStyle={{ gap: GAP }}
        contentContainerStyle={{ gap: GAP, padding: PADDING }}
        ListHeaderComponent={
          <View style={{ gap: 12 }}>
            <View style={local.headerRow}>
              <Text style={styles.title}>Wardrobe{items ? ` (${items.length})` : ""}</Text>
              {items !== null && (
                <ConfirmButton
                  label="Start over"
                  confirmLabel="Clear everything?"
                  danger
                  compact
                  accessibilityLabel="Start over: clear every like and dislike"
                  onConfirm={() => void startOver()}
                />
              )}
            </View>
            <AccountBanner />
            <CurrencyPicker />
            {error && <Text style={styles.error}>{error}</Text>}
            {items !== null && (
              <WardrobeFilters items={items} shown={shown.length} filter={filter} onChange={setFilter} />
            )}
            {items !== null && (
              // What a pop-up would have explained, said once for the whole screen.
              <Text style={local.hint}>
                {items.length > 0 &&
                  "Removed items still count towards your taste, and may come back in the feed after 20 more swipes. "}
                Start over clears every like and dislike, and the feed goes back to best-sellers. Saved sets stay.
              </Text>
            )}
          </View>
        }
        ListEmptyComponent={
          items === null ? null : items.length > 0 ? (
            <Text style={styles.subtitle}>Nothing in your wardrobe matches these filters.</Text>
          ) : (
            <Text style={styles.subtitle}>Nothing here yet. Tap ♡ on the Feed tab and it lands here.</Text>
          )
        }
        renderItem={({ item }) => (
          <View style={{ width: tileWidth, gap: 6 }}>
            <ProductTile product={item} width={tileWidth} />
            <ConfirmButton
              label="Remove"
              accessibilityLabel={`Remove ${item.name}`}
              onConfirm={() => void remove(item)}
            />
          </View>
        )}
      />
    </SafeAreaView>
  );
}

const local = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  hint: { color: colors.muted, fontSize: 13 },
});
