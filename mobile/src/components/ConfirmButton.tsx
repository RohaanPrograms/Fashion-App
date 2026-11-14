// A button that asks "Are you sure?" by changing itself, instead of opening a
// pop-up. First tap: it turns red and asks. Second tap: it does the thing.
// Left alone for a few seconds, it goes back to normal, so a stray tap never
// leaves it primed.
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text } from "react-native";

import { colors } from "../theme";

const DISARM_AFTER_MS = 4000;

type Props = {
  label: string; // "Remove"
  confirmLabel?: string; // "Are you sure?"
  onConfirm: () => void;
  accessibilityLabel?: string;
  // "danger": red text even before the first tap, for actions that can't be
  // undone (Start over). "compact": sized for a header, not a full-width row.
  danger?: boolean;
  compact?: boolean;
};

export function ConfirmButton({
  label,
  confirmLabel = "Are you sure?",
  onConfirm,
  accessibilityLabel,
  danger = false,
  compact = false,
}: Props) {
  const [armed, setArmed] = useState(false);

  // While armed, a timer puts the button back. The cleanup cancels it if the
  // button is tapped again, or disappears, first.
  useEffect(() => {
    if (!armed) return;
    const timer = setTimeout(() => setArmed(false), DISARM_AFTER_MS);
    return () => clearTimeout(timer);
  }, [armed]);

  function press() {
    if (!armed) {
      setArmed(true);
      return;
    }
    setArmed(false);
    onConfirm();
  }

  return (
    <Pressable
      onPress={press}
      accessibilityRole="button"
      accessibilityLabel={armed ? `${confirmLabel} Tap again to confirm.` : accessibilityLabel ?? label}
      hitSlop={6}
      style={({ pressed }) => [s.button, compact && s.compact, armed && s.armed, pressed && s.pressed]}
    >
      <Text style={[s.text, danger && s.textDanger, armed && s.textArmed]}>{armed ? confirmLabel : label}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  button: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingVertical: 7,
    alignItems: "center",
    backgroundColor: colors.background,
  },
  compact: { paddingHorizontal: 12, paddingVertical: 6 },
  armed: { backgroundColor: colors.error, borderColor: colors.error },
  pressed: { opacity: 0.6 },
  text: { fontSize: 13, color: colors.text },
  textDanger: { color: colors.error, fontWeight: "600" },
  textArmed: { color: colors.primaryText, fontWeight: "600" },
});
