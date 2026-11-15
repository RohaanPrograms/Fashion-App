// The set builder's rules, as pure functions.
//
// They mirror backend/app/recs/outfits.py (and the name limit in
// backend/app/schemas/outfits.py) so the screen can guide you before you
// press Save. The server checks every rule again, so a mismatch here could
// only make the screen less helpful, never let a bad set through.
//
// Rows, head to toe: Top · Full body · Layer · Bottom · Shoes · Accessory.
// One item per row. Outer pieces (jackets, blazers, cardigans, hoodies) go in
// Layer; jumpers and shirts can go in either Top or Layer, and you choose by
// tapping them in that row. A full-body item (a dress) can't go with a
// Bottom, but can have a Top under it and a Layer over it.
//
// Accessories are the exception to "one per row": they go by kind. One bag,
// one hat, one pair of sunglasses, one belt, one scarf; as much jewellery and
// as many hair accessories as you like. (The server caps a set at 20 items as
// a safety net, not a design limit.)

import type { Outfit, Product } from "../api/client";

export type Slot = "top" | "full_body" | "layer" | "bottom" | "shoes" | "accessory";

export const SLOT_BY_CATEGORY: Record<string, Slot> = {
  "Garment Upper body": "top",
  "Garment Lower body": "bottom",
  "Garment Full body": "full_body",
  Shoes: "shoes",
  Accessories: "accessory",
};

// Upper-body garment types that aren't plain tops; the first is the default.
const UPPER_BODY_SLOTS_BY_TYPE: Record<string, Slot[]> = {
  Jacket: ["layer"],
  Blazer: ["layer"],
  Cardigan: ["layer"],
  Hoodie: ["layer"],
  Sweater: ["layer", "top"], // a jumper: usually over something
  Shirt: ["top", "layer"], // usually on its own; open over a tank
};

// Head to toe: the order rows appear in, and items are sent in.
export const SLOT_ORDER: Slot[] = ["top", "full_body", "layer", "bottom", "shoes", "accessory"];

export const SLOT_LABELS: Record<Slot, string> = {
  top: "Top",
  full_body: "Full body",
  layer: "Layer",
  bottom: "Bottom",
  shoes: "Shoes",
  accessory: "Accessory",
};

// Accessory kinds (H&M garment type -> kind) and whether a set can hold
// several of that kind. A type not listed counts as "other": one.
const ACCESSORY_KIND_BY_TYPE: Record<string, string> = {
  Bag: "bag",
  "Hat/brim": "hat", "Hat/beanie": "hat", "Bucket hat": "hat", "Straw hat": "hat",
  "Felt hat": "hat", "Cap/peaked": "hat", Cap: "hat",
  Earring: "jewellery", Earrings: "jewellery", Necklace: "jewellery", Ring: "jewellery", Bracelet: "jewellery",
  Sunglasses: "sunglasses",
  Belt: "belt", Braces: "belt",
  Scarf: "scarf", "Other accessories": "scarf",
  "Hair/alice band": "hair", "Hair string": "hair", "Hair ties": "hair", "Hair clip": "hair", Hairband: "hair",
};
const STACKING_KINDS = new Set(["jewellery", "hair"]);

function accessoryKind(p: Product): string {
  return ACCESSORY_KIND_BY_TYPE[p.type ?? ""] ?? "other";
}

export const MIN_ITEMS = 2;
export const MAX_NAME_LENGTH = 60;

type SingleSlot = Exclude<Slot, "accessory">;

/** What's picked: one item per row, except accessories, which are a list. */
export type Selection = Partial<Record<SingleSlot, Product>> & { accessory?: Product[] };

/** Is this tile picked in this row? */
export function isPicked(sel: Selection, slot: Slot, p: Product): boolean {
  if (slot === "accessory") return (sel.accessory ?? []).some((a) => a.id === p.id);
  return sel[slot]?.id === p.id;
}

/** Does this row have anything picked (for its ✓)? */
export function rowHasPick(sel: Selection, slot: Slot): boolean {
  if (slot === "accessory") return (sel.accessory ?? []).length > 0;
  return sel[slot] !== undefined;
}

/** Every row this garment can go in, the default first; [] if none. */
export function slotsOf(p: Product): Slot[] {
  const slot = SLOT_BY_CATEGORY[p.category ?? ""];
  if (!slot) return [];
  if (slot === "top") return UPPER_BODY_SLOTS_BY_TYPE[p.type ?? ""] ?? ["top"];
  return [slot];
}

/** The row a garment goes in when it isn't tapped in a particular row. */
export function slotOf(p: Product): Slot | null {
  return slotsOf(p)[0] ?? null;
}

export function groupBySlot(products: Product[]): Record<Slot, Product[]> {
  const rows: Record<Slot, Product[]> = { top: [], full_body: [], layer: [], bottom: [], shoes: [], accessory: [] };
  for (const p of products) {
    // A jumper or shirt is offered in both of its rows.
    for (const slot of slotsOf(p)) rows[slot].push(p);
  }
  return rows;
}

/** Tap an item in a row: select it there (replacing whatever was in that row,
 *  and moving it out of any other row), or deselect it if it was there. */
export function toggle(sel: Selection, p: Product, slot: Slot | null = slotOf(p)): Selection {
  if (!slot || !slotsOf(p).includes(slot)) return sel;
  const next: Selection = { ...sel };
  if (slot === "accessory") {
    const worn = sel.accessory ?? [];
    if (worn.some((a) => a.id === p.id)) {
      next.accessory = worn.filter((a) => a.id !== p.id);
      return next;
    }
    const kind = accessoryKind(p);
    // One bag, one hat...: a second of a one-only kind replaces the first.
    const kept = STACKING_KINDS.has(kind) ? worn : worn.filter((a) => accessoryKind(a) !== kind);
    next.accessory = [...kept, p];
    return next;
  }
  if (sel[slot]?.id === p.id) {
    delete next[slot];
    return next;
  }
  for (const other of SINGLE_SLOTS) if (next[other]?.id === p.id) delete next[other];
  next[slot] = p;
  // A dress covers the legs: it and a bottom replace each other.
  if (slot === "full_body") delete next.bottom;
  if (slot === "bottom") delete next.full_body;
  return next;
}

const SINGLE_SLOTS = SLOT_ORDER.filter((s): s is SingleSlot => s !== "accessory");

/** Every picked item with its row, head to toe (accessories last, in the order picked). */
function chosenWithSlots(sel: Selection): [Product, Slot][] {
  const singles = SINGLE_SLOTS.flatMap((slot): [Product, Slot][] => {
    const p = sel[slot]; // a local, so TypeScript knows it isn't undefined below
    return p ? [[p, slot]] : [];
  });
  return [...singles, ...(sel.accessory ?? []).map((p): [Product, Slot] => [p, "accessory"])];
}

function chosen(sel: Selection): Product[] {
  return chosenWithSlots(sel).map(([p]) => p);
}

export function selectedIds(sel: Selection): string[] {
  return chosen(sel).map((p) => p.id);
}

/** The row each picked item is in, in the same order as selectedIds: sent to
 *  the server so a jumper saved as a Layer stays a Layer. */
export function selectedSlots(sel: Selection): Slot[] {
  return chosenWithSlots(sel).map(([, slot]) => slot);
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

// --- Editing a saved set ---------------------------------------------------------

/** A saved set, as the builder's selection: each item in its row. A slot the
 *  app doesn't know (say, a newer server) is skipped rather than crashing. */
export function selectionFromOutfit(outfit: Outfit): Selection {
  const sel: Selection = {};
  for (const item of outfit.items) {
    const allowed = slotsOf(item.product);
    // A set saved before layering existed may file a jacket as a "top": put
    // it in a row it's allowed in, so saving it again isn't refused.
    const slot = allowed.includes(item.slot as Slot) ? (item.slot as Slot) : allowed[0];
    if (slot === "accessory") sel.accessory = [...(sel.accessory ?? []), item.product];
    else if (slot && sel[slot] === undefined) sel[slot] = item.product;
  }
  return sel;
}

/** The builder's choices when editing: the wardrobe, plus any of the set's
 *  items that have since left it, so editing never silently drops a piece. */
export function withSetItems(wardrobe: Product[], outfit: Outfit): Product[] {
  const have = new Set(wardrobe.map((p) => p.id));
  return [...wardrobe, ...outfit.items.map((i) => i.product).filter((p) => !have.has(p.id))];
}

// --- Picked first, and the review page ---------------------------------------------

/** A row as the builder draws it: what's picked first (in the order picked),
 *  then everything else in its original order. Unpick an item and it goes
 *  back to its place. So a row's picks are always visible at its start. */
export function orderRow(products: Product[], sel: Selection, slot: Slot): Product[] {
  const picked = products.filter((p) => isPicked(sel, slot, p));
  if (slot === "accessory") {
    const order = (sel.accessory ?? []).map((a) => a.id);
    picked.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
  }
  return [...picked, ...products.filter((p) => !isPicked(sel, slot, p))];
}

export type ReviewGroup = { slot: Slot; label: string; items: Product[] };

/** The review page: every pick, head to toe, grouped by row; empty rows left out. */
export function reviewGroups(sel: Selection): ReviewGroup[] {
  const groups: ReviewGroup[] = [];
  for (const slot of SLOT_ORDER) {
    const items = slot === "accessory" ? sel.accessory ?? [] : sel[slot] ? [sel[slot]!] : [];
    if (items.length === 0) continue;
    const label = slot === "accessory" && items.length > 1 ? "Accessories" : SLOT_LABELS[slot];
    groups.push({ slot, label, items });
  }
  return groups;
}
