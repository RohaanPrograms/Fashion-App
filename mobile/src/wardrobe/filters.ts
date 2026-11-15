// The wardrobe's filters, as pure functions.
//
// The choices are built from what's actually in the wardrobe (tens of items,
// all loaded already), so there's never a button that would show nothing,
// and each one carries a count. Combining follows the usual shop rule:
//   within a section, ANY choice matches   (Black + White = black or white)
//   across sections, EVERY one must match  (Tops + Black = black tops)

import type { Product } from "../api/client";

export type FacetKey = "category" | "type" | "colour" | "pattern";

export const FACETS: { key: FacetKey; label: string }[] = [
  { key: "category", label: "Category" },
  { key: "type", label: "Type" },
  { key: "colour", label: "Colour" },
  { key: "pattern", label: "Pattern" },
];

// The same names as the feed's filter buttons.
const CATEGORY_LABELS: Record<string, string> = {
  "Garment Upper body": "Tops",
  "Garment Lower body": "Bottoms",
  "Garment Full body": "Dresses",
  Shoes: "Shoes",
  Accessories: "Accessories",
};

export type WardrobeFilter = Record<FacetKey, string[]>;

export const NO_WARDROBE_FILTER: WardrobeFilter = { category: [], type: [], colour: [], pattern: [] };

/** What an item counts as in one section; null = it has nothing to offer there. */
export function valueOf(p: Product, key: FacetKey): string | null {
  switch (key) {
    case "category":
      return p.category ? CATEGORY_LABELS[p.category] ?? p.category : null;
    case "type":
      return p.type;
    case "colour":
      return p.colour_family; // "Beige", not "Light Beige"
    case "pattern":
      return p.pattern;
  }
}

export type FacetOption = { value: string; count: number };

/** One section's buttons: the values in the wardrobe, most common first (ties
 *  A–Z). A picked value stays listed even if nothing has it any more (count 0),
 *  so it can still be turned off. */
export function facetOptions(items: Product[], key: FacetKey, filter: WardrobeFilter): FacetOption[] {
  const counts = new Map<string, number>();
  for (const p of items) {
    const v = valueOf(p, key);
    if (v) counts.set(v, (counts.get(v) ?? 0) + 1);
  }
  for (const picked of filter[key]) if (!counts.has(picked)) counts.set(picked, 0);
  return [...counts.entries()]
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));
}

export function matches(p: Product, filter: WardrobeFilter): boolean {
  return FACETS.every(({ key }) => {
    const picked = filter[key];
    if (picked.length === 0) return true;
    const v = valueOf(p, key);
    return v !== null && picked.includes(v);
  });
}

export function applyFilter(items: Product[], filter: WardrobeFilter): Product[] {
  return items.filter((p) => matches(p, filter));
}

/** Tap a button: turn that value on, or off if it was on. */
export function toggleValue(filter: WardrobeFilter, key: FacetKey, value: string): WardrobeFilter {
  const picked = filter[key];
  const next = picked.includes(value) ? picked.filter((v) => v !== value) : [...picked, value];
  return { ...filter, [key]: next };
}

/** How many buttons are on, across all sections (the number on "Filter"). */
export function activeCount(filter: WardrobeFilter): number {
  return FACETS.reduce((n, { key }) => n + filter[key].length, 0);
}

export function shownSummary(shown: number, total: number): string {
  return `Showing ${shown} of ${total}`;
}
