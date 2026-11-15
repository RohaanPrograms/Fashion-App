// "Prices in CA$ · Change" on the Wardrobe tab: opens the list of offered
// currencies; picking one updates every price in the app and is remembered
// on this device. Converted prices are approximate (see src/currency.ts).
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { CURRENCIES, DEFAULT_CURRENCY } from "../currency";
import { setDisplayCurrency, useDisplayCurrency } from "../currencyStore";
import { colors } from "../theme";

export function CurrencyPicker() {
  const display = useDisplayCurrency();
  const [open, setOpen] = useState(false);
  const current = CURRENCIES.find((c) => c.code === display);
  const symbol = current ? current.label.split(" ")[0] : display;

  return (
    <View style={c.wrap}>
      <View style={c.line}>
        <Text style={c.text}>
          Prices in {symbol}
          {display !== DEFAULT_CURRENCY ? " (approximate)" : ""}
        </Text>
        <Pressable onPress={() => setOpen((o) => !o)} accessibilityRole="button" hitSlop={8}>
          <Text style={c.link}>{open ? "Done" : "Change"}</Text>
        </Pressable>
      </View>
      {open && (
        <View style={c.chips}>
          {CURRENCIES.map(({ code, label }) => {
            const on = code === display;
            return (
              <Pressable
                key={code}
                onPress={() => {
                  setDisplayCurrency(code);
                  setOpen(false);
                }}
                accessibilityRole="button"
                aria-selected={on}
                style={({ pressed }) => [c.chip, on && c.chipOn, pressed && { opacity: 0.6 }]}
              >
                <Text style={[c.chipText, on && c.chipTextOn]}>{label}</Text>
              </Pressable>
            );
          })}
        </View>
      )}
    </View>
  );
}

const c = StyleSheet.create({
  wrap: { gap: 8 },
  line: { flexDirection: "row", alignItems: "center", gap: 10 },
  text: { fontSize: 13, color: colors.muted },
  link: { fontSize: 13, color: colors.primary, fontWeight: "600", textDecorationLine: "underline" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  chipOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: 13, color: colors.text },
  chipTextOn: { color: colors.primaryText, fontWeight: "600" },
});
