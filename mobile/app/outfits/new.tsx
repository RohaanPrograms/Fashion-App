// The set builder: one labelled row per slot (Top, Full body, Bottom, Shoes,
// Accessory), filled from your wardrobe. Tap to pick, tap again to unpick.
// The rules and the total are the tested functions in src/outfits/builder.ts;
// the server checks them all again when you save.
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from "react-native";

import { api, type ApiError, type Product } from "../../src/api/client";
import { useAuth } from "../../src/auth/AuthContext";
import { ProductTile } from "../../src/components/ProductTile";
import { formatPrice } from "../../src/format";
import {
  MAX_NAME_LENGTH,
  SLOT_LABELS,
  SLOT_ORDER,
  groupBySlot,
  problem,
  selectedIds,
  toggle,
  totalPrice,
  type Selection,
} from "../../src/outfits/builder";
import { colors, styles } from "../../src/theme";

const MAX_WIDTH = 430; // phone width; a centred column on desktop
const TILE_WIDTH = 110;

export default function NewSet() {
  const { getValidToken, loading } = useAuth();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const columnWidth = Math.min(width, MAX_WIDTH);

  const [wardrobe, setWardrobe] = useState<Product[] | null>(null);
  const [selection, setSelection] = useState<Selection>({});
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // After a reload on this page the saved session is still being checked
  // (`loading`), and there's no token yet. The tabs wait behind a spinner;
  // this page isn't a tab, so it waits here.
  useEffect(() => {
    if (loading) return;
    (async () => {
      try {
        const token = await getValidToken();
        setWardrobe((await api.wardrobe(token)).items);
      } catch (err) {
        setError((err as ApiError).detail ?? "Couldn't load your wardrobe.");
      }
    })();
  }, [loading]);

  const rows = wardrobe ? groupBySlot(wardrobe) : null;
  const total = totalPrice(selection);
  const currency = wardrobe?.[0]?.currency ?? "GBP";
  const issue = problem(selection, name);

  function done() {
    // Back to the Sets tab. After a reload there's no page to go back to, so
    // go there directly instead of leaving the visitor stuck.
    if (router.canGoBack()) router.back();
    else router.replace("/outfits");
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const token = await getValidToken();
      await api.createOutfit(token, name.trim(), selectedIds(selection));
      done();
    } catch (err) {
      setError((err as ApiError).detail ?? "Couldn't save the set.");
    } finally {
      setSaving(false);
    }
  }

  let content;
  if (rows === null) {
    content = error ? null : <ActivityIndicator style={{ marginTop: 24 }} />;
  } else if (wardrobe!.length === 0) {
    content = (
      <Text style={[styles.subtitle, { marginTop: 20 }]}>
        Your wardrobe is empty. Like a few items on the Feed tab first.
      </Text>
    );
  } else {
    content = SLOT_ORDER.filter((slot) => rows[slot].length > 0).map((slot) => (
      <View key={slot} style={{ marginTop: 20 }}>
        <Text style={s.rowLabel}>
          {SLOT_LABELS[slot]}
          {selection[slot] ? "  ✓" : ""}
        </Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10 }}>
          {rows[slot].map((p) => (
            <ProductTile
              key={p.id}
              product={p}
              width={TILE_WIDTH}
              selected={selection[slot]?.id === p.id}
              onPress={() => setSelection((current) => toggle(current, p))}
            />
          ))}
        </ScrollView>
      </View>
    ));
  }

  return (
    <View style={s.screen}>
      <View style={[s.column, { width: columnWidth }]}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 32 }}>
          <Text style={styles.label}>Name</Text>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            placeholder="Friday night"
            placeholderTextColor={colors.muted}
            maxLength={MAX_NAME_LENGTH}
            accessibilityLabel="Set name"
          />
          {content}
        </ScrollView>
        {/* Stays put while the rows scroll. */}
        <View style={s.footer}>
          <Text style={s.total}>Total {total === null ? "—" : formatPrice(total, currency)}</Text>
          {issue && <Text style={styles.info}>{issue}</Text>}
          {error && <Text style={styles.error}>{error}</Text>}
          <Pressable
            style={[styles.button, { marginTop: 12 }, (issue !== null || saving) && styles.buttonDisabled]}
            disabled={issue !== null || saving}
            onPress={save}
            accessibilityRole="button"
          >
            <Text style={styles.buttonText}>{saving ? "Saving…" : "Save set"}</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background, alignItems: "center" },
  column: { flex: 1 },
  rowLabel: { fontSize: 15, fontWeight: "600", color: colors.text, marginBottom: 8 },
  footer: { borderTopWidth: 1, borderColor: colors.border, padding: 16 },
  total: { fontSize: 18, fontWeight: "700", color: colors.text },
});
