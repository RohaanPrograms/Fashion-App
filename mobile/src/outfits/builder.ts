// The set builder's rules, as pure functions.
//
// They mirror backend/app/recs/outfits.py (and the name limit in
// backend/app/schemas/outfits.py) so the screen can guide you before you
// press Save. The server checks every rule again, so a mismatch here could
// only make the screen less helpful, never let a bad set through.
//
// With one item per row and the full-body rule, a set holds at most 4 items
// (top, bottom, shoes, accessory), so the server's 5-item cap never bites.

import type { Product } from "../api/client";

export type Slot = "top" | "full_body" | "bottom" | "shoes" | "accessory";

export const SLOT_BY_CATEGORY: Record<string, Slot> = {
  "Garment Upper body": "top",
  "Garment Lower body": "bottom",
  "Garment Full body": "full_body",
  Shoes: "shoes",
  Accessories: "accessory",
};

// Head to toe: the order rows appear in, and ids are sent in.
export const SLOT_ORDER: Slot[] = ["top", "full_body", "bottom", "shoes", "accessory"];

export const SLOT_LABELS: Record<Slot, string> = {
  top: "Top",
  full_body: "Full body",
  bottom: "Bottom",
  shoes: "Shoes",
  accessory: "Accessory",
};

export const MIN_ITEMS = 2;
export const MAX_NAME_LENGTH = 60;

// A full-body item already covers these two slots.
const COVERED_BY_FULL_BODY: Slot[] = ["top", "bottom"];

export type Selection = Partial<Record<Slot, Product>>;

export function slotOf(p: Product): Slot | null {
  return SLOT_BY_CATEGORY[p.category ?? ""] ?? null;
}

export function groupBySlot(products: Product[]): Record<Slot, Product[]> {
  const rows: Record<Slot, Product[]> = { top: [], full_body: [], bottom: [], shoes: [], accessory: [] };
  for (const p of products) {
    const slot = slotOf(p);
    if (slot) rows[slot].push(p);
  }
  return rows;
}

/** Tap an item: select it (replacing whatever was in its row), or deselect it. */
export function toggle(sel: Selection, p: Product): Selection {
  const slot = slotOf(p);
  if (!slot) return sel;
  const next: Selection = { ...sel };
  if (sel[slot]?.id === p.id) {
    delete next[slot];
    return next;
  }
  next[slot] = p;
  if (slot === "full_body") {
    for (const covered of COVERED_BY_FULL_BODY) delete next[covered];
  } else if (COVERED_BY_FULL_BODY.includes(slot)) {
    delete next.full_body;
  }
  return next;
}

function chosen(sel: Selection): Product[] {
  return SLOT_ORDER.flatMap((slot) => {
    const p = sel[slot]; // a local, so TypeScript knows it isn't undefined below
    return p ? [p] : [];
  });
}

export function selectedIds(sel: Selection): string[] {
  return chosen(sel).map((p) => p.id);
}

/** Sum of the known prices, or null if none is known: the server's rule. */
export function totalPrice(sel: Selection): number | null {
  const prices = chosen(sel)
    .map((p) => p.price)
    .filter((price): price is number => price !== null);
  if (prices.length === 0) return null;
  // Rounded to pence, so 0.1 + 0.2 shows as 0.3, not 0.30000000000000004.
  return Math.round(prices.reduce((a, b) => a + b, 0) * 100) / 100;
}

/** Why the set can't be saved yet, in plain words; null when it can. */
export function problem(sel: Selection, name: string): string | null {
  const trimmed = name.trim(); // the server ignores surrounding spaces too
  if (trimmed.length === 0) return "Give the set a name.";
  if (trimmed.length > MAX_NAME_LENGTH) return `Keep the name to ${MAX_NAME_LENGTH} characters or fewer.`;
  if (chosen(sel).length < MIN_ITEMS) return "Pick at least 2 items, one per row.";
  return null;
}
