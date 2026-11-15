// The set builder, shared by two pages: /outfits/new (a fresh set) and
// /outfits/{id}/edit (a saved set, pre-filled). One labelled row per slot
// (Top, Full body, Bottom, Shoes, Accessory), filled from the wardrobe. Tap
// to pick, tap again to unpick. A jumper or shirt shows in both Top and
// Layer: the row you tap it in is the role it plays. The rules and the total are the tested
// functions in builder.ts; the server checks them all again when you save.
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

import { api, type ApiError, type Product } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ProductTile } from "../components/ProductTile";
import { formatPrice } from "../format";
import { colors, styles } from "../theme";
import {
  MAX_NAME_LENGTH,
  SLOT_LABELS,
  SLOT_ORDER,
  groupBySlot,
  isPicked,
  problem,
  rowHasPick,
  selectedIds,
  selectedSlots,
  selectionFromOutfit,
  toggle,
  totalPrice,
  withSetItems,
  type Selection,
} from "./builder";

const MAX_WIDTH = 430; // phone width; a centred column on desktop
const TILE_WIDTH = 110;

/** `outfitId` given: edit that saved set. Not given: build a new one. */
export function BuilderScreen({ outfitId }: { outfitId?: string }) {
  const { getValidToken, loading } = useAuth();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const columnWidth = Math.min(width, MAX_WIDTH);
  const editing = outfitId !== undefined;

  // What can be picked: the wardrobe (plus, when editing, the set's own items).
  const [choices, setChoices] = useState<Product[] | null>(null);
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
        const wardrobe = (await api.wardrobe(token)).items;
        if (!editing) {
          setChoices(wardrobe);
          return;
        }
        // There's no "get one set" endpoint; the list is small, so find it there.
        const outfit = (await api.outfits(token)).outfits.find((o) => o.id === outfitId);
        if (!outfit) {
          setError("This set doesn't exist any more. It may have been deleted.");
          return;
        }
        setName(outfit.name);
        setSelection(selectionFromOutfit(outfit));
        setChoices(withSetItems(wardrobe, outfit));
      } catch (err) {
        setError((err as ApiError).detail ?? "Couldn't load your wardrobe.");
      }
    })();
  }, [loading, outfitId]);

  const rows = choices ? groupBySlot(choices) : null;
  const total = totalPrice(selection);
  const currency = choices?.[0]?.currency ?? "GBP";
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
      const ids = selectedIds(selection);
      const slots = selectedSlots(selection);
      if (outfitId !== undefined) await api.updateOutfit(token, outfitId, name.trim(), ids, slots);
      else await api.createOutfit(token, name.trim(), ids, slots);
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
  } else if (choices!.length === 0) {
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
          {rowHasPick(selection, slot) ? "  ✓" : ""}
        </Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10 }}>
          {rows[slot].map((p) => (
            <ProductTile
              key={p.id}
              product={p}
              width={TILE_WIDTH}
              selected={isPicked(selection, slot, p)}
              onPress={() => setSelection((current) => toggle(current, p, slot))}
            />
          ))}
        </ScrollView>
      </View>
    ));
  }

  const saveLabel = saving ? "Saving…" : editing ? "Save changes" : "Save set";

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
            <Text style={styles.buttonText}>{saveLabel}</Text>
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
