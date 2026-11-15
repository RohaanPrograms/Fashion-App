// The wardrobe's filters: choices come from what's actually in the wardrobe
// (with counts); within a section any choice matches, across sections all must.
import type { Product } from "../src/api/client";
import {
  NO_WARDROBE_FILTER,
  activeCount,
  applyFilter,
  facetOptions,
  shownSummary,
  toggleValue,
} from "../src/wardrobe/filters";

function item(id: string, category: string, type: string, colour_family: string | null, pattern: string): Product {
  return {
    id, name: id, brand: "H&M", price: 10, currency: "GBP", image_url: null,
    category, colour: null, type, pattern, description: null, colour_family,
  };
}
const blackTee = item("blackTee", "Garment Upper body", "T-shirt", "Black", "Solid");
const whiteTee = item("whiteTee", "Garment Upper body", "T-shirt", "White", "Solid");
const stripedTop = item("stripedTop", "Garment Upper body", "Vest top", "White", "Stripe");
const jeans = item("jeans", "Garment Lower body", "Trousers", "Blue", "Denim");
const blackBoots = item("blackBoots", "Shoes", "Boots", "Black", "Solid");
const mystery = item("mystery", "Accessories", "Bag", null, "Solid");
const wardrobe = [blackTee, whiteTee, stripedTop, jeans, blackBoots, mystery];
const ids = (ps: Product[]) => ps.map((p) => p.id);

test("choices come from the wardrobe, most common first, with counts", () => {
  expect(facetOptions(wardrobe, "category", NO_WARDROBE_FILTER)).toEqual([
    { value: "Tops", count: 3 },
    { value: "Accessories", count: 1 },
    { value: "Bottoms", count: 1 },
    { value: "Shoes", count: 1 },
  ]);
  expect(facetOptions(wardrobe, "colour", NO_WARDROBE_FILTER)).toEqual([
    { value: "Black", count: 2 },
    { value: "White", count: 2 },
    { value: "Blue", count: 1 },
  ]);
});

test("an item with no known colour gets no colour button", () => {
  const values = facetOptions(wardrobe, "colour", NO_WARDROBE_FILTER).map((o) => o.value);
  expect(values).not.toContain(null);
});

test("no filter shows everything", () => {
  expect(ids(applyFilter(wardrobe, NO_WARDROBE_FILTER))).toEqual(ids(wardrobe));
});

test("within a section, any choice matches", () => {
  const f = toggleValue(toggleValue(NO_WARDROBE_FILTER, "colour", "Black"), "colour", "White");
  expect(ids(applyFilter(wardrobe, f))).toEqual(["blackTee", "whiteTee", "stripedTop", "blackBoots"]);
});

test("across sections, every section must match", () => {
  const f = toggleValue(toggleValue(NO_WARDROBE_FILTER, "category", "Tops"), "colour", "Black");
  expect(ids(applyFilter(wardrobe, f))).toEqual(["blackTee"]);
});

test("a colour filter leaves out items with no known colour", () => {
  const f = toggleValue(NO_WARDROBE_FILTER, "colour", "Black");
  expect(ids(applyFilter(wardrobe, f))).not.toContain("mystery");
});

test("tapping a choice again turns it off", () => {
  const on = toggleValue(NO_WARDROBE_FILTER, "pattern", "Stripe");
  expect(activeCount(on)).toBe(1);
  expect(toggleValue(on, "pattern", "Stripe")).toEqual(NO_WARDROBE_FILTER);
});

test("a picked choice stays visible even when nothing has it any more", () => {
  const f = toggleValue(NO_WARDROBE_FILTER, "type", "Hoodie");
  expect(facetOptions(wardrobe, "type", f)).toContainEqual({ value: "Hoodie", count: 0 });
});

test("the summary says how many are showing", () => {
  expect(shownSummary(7, 23)).toBe("Showing 7 of 23");
  expect(shownSummary(1, 1)).toBe("Showing 1 of 1");
});
