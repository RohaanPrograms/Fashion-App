// The filter buttons above the feed.
//
// Row 1, categories: tapping one opens its garment types in row 2. A category
// with something switched on is filled in and shows a count ("Tops · 2").
// Row 2, types: on/off switches; several can be on, across categories.
// Under them, what's showing ("T-shirts and Sunglasses") and a Clear button.
//
// Like ProductCard, it only draws and reports taps; the rules for what each
// tap does are in src/feed/filters.ts. Each row scrolls sideways when it's
// wider than the screen.
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import type { CategoryOption } from "../api/client";
import { NO_PICKS, picksIn, picksSummary, togglePick, type Picks } from "../feed/filters";
import { colors } from "../theme";

type Props = {
  options: CategoryOption[];
  picks: Picks;
  onChange: (next: Picks) => void;
};

export function FilterBar({ options, picks, onChange }: Props) {
  // Which category's types are showing in row 2. Only affects the buttons,
  // not the feed, so it lives here rather than in useFeed.
  const [open, setOpen] = useState<string | null>(null);
  if (options.length === 0) return null;
  const category = options.find((c) => c.key === open);

  function clear() {
    setOpen(null);
    onChange(NO_PICKS);
  }

  return (
    <View>
      <Row>
        <Chip label="All" on={picks.length === 0} onPress={clear} />
        {options.map((c) => {
          const count = picksIn(picks, c.key);
          return (
            <Chip
              key={c.key}
              label={count > 0 ? `${c.label} · ${count}` : c.label}
              on={count > 0}
              open={open === c.key}
              onPress={() => setOpen(open === c.key ? null : c.key)}
            />
          );
        })}
      </Row>
      {category && (
        <Row>
          <Chip
            label={`All ${category.label.toLowerCase()}`}
            on={picks.includes(category.key)}
            small
            onPress={() => onChange(togglePick(picks, category.key))}
          />
          {category.types.map((t) => {
            const pick = `${category.key}:${t.key}`;
            return (
              <Chip
                key={pick}
                label={t.label}
                on={picks.includes(pick)}
                small
                onPress={() => onChange(togglePick(picks, pick))}
              />
            );
          })}
        </Row>
      )}
      {picks.length > 0 && (
        <View style={bar.summary}>
          <Text style={bar.summaryText} numberOfLines={1}>
            Showing: {picksSummary(picks, options)}
          </Text>
          <Pressable onPress={clear} accessibilityRole="button" hitSlop={8}>
            <Text style={bar.clear}>Clear</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={bar.row}
      contentContainerStyle={bar.rowContent}
    >
      {children}
    </ScrollView>
  );
}

type ChipProps = { label: string; on: boolean; open?: boolean; small?: boolean; onPress: () => void };

function Chip({ label, on, open, small, onPress }: ChipProps) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: on, expanded: open }}
      style={({ pressed }) => [
        bar.chip,
        small && bar.chipSmall,
        open && bar.chipOpen,
        on && bar.chipOn,
        pressed && bar.pressed,
      ]}
    >
      <Text style={[bar.text, small && bar.textSmall, on && bar.textOn]}>{label}</Text>
    </Pressable>
  );
}

const bar = StyleSheet.create({
  row: { flexGrow: 0, marginTop: 8 },
  rowContent: { gap: 8, paddingHorizontal: 2 },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 7,
    backgroundColor: colors.background,
  },
  chipSmall: { paddingHorizontal: 12, paddingVertical: 5 },
  // Open but nothing picked in it: a darker outline, so you can tell which
  // category row 2 belongs to.
  chipOpen: { borderColor: colors.primary, borderWidth: 2 },
  chipOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  pressed: { opacity: 0.6 },
  text: { fontSize: 14, color: colors.text },
  textSmall: { fontSize: 13 },
  textOn: { color: colors.primaryText, fontWeight: "600" },
  summary: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 12, marginTop: 8 },
  summaryText: { color: colors.text, fontSize: 13, flexShrink: 1 },
  clear: { color: colors.primary, fontSize: 13, fontWeight: "600", textDecorationLine: "underline" },
});
