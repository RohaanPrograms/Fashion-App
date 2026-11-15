// The wardrobe's filter controls: a "Filter" button that opens a panel of
// on/off buttons (Category, Type, Colour, Pattern), each with a count, built
// from what's in the wardrobe; and a "Showing 7 of 23 · Clear" line. It only
// draws and reports taps; the rules are in src/wardrobe/filters.ts.
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { Product } from "../api/client";
import { colors } from "../theme";
import {
  FACETS,
  NO_WARDROBE_FILTER,
  activeCount,
  facetOptions,
  shownSummary,
  toggleValue,
  type WardrobeFilter,
} from "../wardrobe/filters";

type Props = {
  items: Product[];
  shown: number;
  filter: WardrobeFilter;
  onChange: (next: WardrobeFilter) => void;
};

export function WardrobeFilters({ items, shown, filter, onChange }: Props) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;
  const active = activeCount(filter);

  return (
    <View style={f.wrap}>
      <View style={f.bar}>
        <Pressable
          onPress={() => setOpen((o) => !o)}
          accessibilityRole="button"
          accessibilityState={{ expanded: open }}
          style={({ pressed }) => [f.toggle, active > 0 && f.toggleOn, pressed && f.pressed]}
        >
          <Text style={[f.toggleText, active > 0 && f.textOn]}>
            {open ? "Hide filters" : "Filter"}
            {active > 0 ? ` · ${active}` : ""}
          </Text>
        </Pressable>
        {active > 0 && (
          <View style={f.summary}>
            <Text style={f.summaryText}>{shownSummary(shown, items.length)}</Text>
            <Pressable onPress={() => onChange(NO_WARDROBE_FILTER)} accessibilityRole="button" hitSlop={8}>
              <Text style={f.clear}>Clear</Text>
            </Pressable>
          </View>
        )}
      </View>

      {open &&
        FACETS.map(({ key, label }) => {
          const options = facetOptions(items, key, filter);
          if (options.length === 0) return null;
          return (
            <View key={key} style={f.section}>
              <Text style={f.sectionLabel}>{label}</Text>
              {/* Wraps onto more lines: a wardrobe has few enough values to show them all. */}
              <View style={f.chips}>
                {options.map(({ value, count }) => {
                  const on = filter[key].includes(value);
                  return (
                    <Pressable
                      key={value}
                      onPress={() => onChange(toggleValue(filter, key, value))}
                      accessibilityRole="button"
                      accessibilityState={{ selected: on }}
                      accessibilityLabel={`${label}: ${value}, ${count} ${count === 1 ? "item" : "items"}`}
                      style={({ pressed }) => [f.chip, on && f.chipOn, pressed && f.pressed]}
                    >
                      <Text style={[f.chipText, on && f.textOn]}>
                        {value} · {count}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          );
        })}
    </View>
  );
}

const f = StyleSheet.create({
  wrap: { gap: 10 },
  bar: { flexDirection: "row", alignItems: "center", gap: 12, flexWrap: "wrap" },
  toggle: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  toggleOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  toggleText: { fontSize: 14, color: colors.text, fontWeight: "600" },
  summary: { flexDirection: "row", alignItems: "center", gap: 10 },
  summaryText: { fontSize: 13, color: colors.text },
  clear: { fontSize: 13, color: colors.primary, fontWeight: "600", textDecorationLine: "underline" },
  section: { gap: 6 },
  sectionLabel: { fontSize: 12, fontWeight: "700", color: colors.muted, letterSpacing: 0.6 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 5,
    backgroundColor: colors.background,
  },
  chipOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: 13, color: colors.text },
  textOn: { color: colors.primaryText },
  pressed: { opacity: 0.6 },
});
