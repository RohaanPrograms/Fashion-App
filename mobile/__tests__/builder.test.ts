// The set builder's rules: one item per row, a dress replaces a top and
// bottom, the total matches the server's, and the reason a set can't be saved
// yet is said in plain words.
import type { Product } from "../src/api/client";
import {
  MAX_NAME_LENGTH,
  groupBySlot,
  problem,
  selectedIds,
  slotOf,
  toggle,
  totalPrice,
  type Selection,
} from "../src/outfits/builder";

function product(id: string, category: string | null, price: number | null = 10): Product {
  return {
    id,
    name: id,
    brand: null,
    price,
    currency: "USD",
    image_url: null,
    category,
    colour: null,
    type: null,
    pattern: null,
    description: null,
  };
}
const tee = product("tee", "Garment Upper body", 9.99);
const shirt = product("shirt", "Garment Upper body", 19.99);
const jeans = product("jeans", "Garment Lower body", 29.99);
const dress = product("dress", "Garment Full body", 39.99);
const boots = product("boots", "Shoes", 49.99);
const bag = product("bag", "Accessories", null);
const odd = product("odd", "Underwear");

test("slots come from the catalogue category", () => {
  expect(slotOf(tee)).toBe("top");
  expect(slotOf(dress)).toBe("full_body");
  expect(slotOf(bag)).toBe("accessory");
  expect(slotOf(odd)).toBeNull();
  expect(slotOf(product("none", null))).toBeNull();
});

test("groupBySlot leaves out items that can't go in a set", () => {
  const rows = groupBySlot([tee, shirt, jeans, odd]);
  expect(rows.top.map((p) => p.id)).toEqual(["tee", "shirt"]);
  expect(rows.bottom.map((p) => p.id)).toEqual(["jeans"]);
  expect(Object.values(rows).flat()).not.toContainEqual(odd);
});

test("picking a second top replaces the first", () => {
  const sel = toggle(toggle({}, tee), shirt);
  expect(sel.top?.id).toBe("shirt");
});

test("tapping the selected item again deselects it", () => {
  expect(toggle(toggle({}, tee), tee).top).toBeUndefined();
});

test("a dress removes the top and bottom", () => {
  const sel = toggle(toggle(toggle(toggle({}, tee), jeans), boots), dress);
  expect(selectedIds(sel)).toEqual(["dress", "boots"]);
});

test("a top removes the dress", () => {
  const sel = toggle(toggle({}, dress), tee);
  expect(selectedIds(sel)).toEqual(["tee"]);
});

test("items that can't go in a set are ignored", () => {
  expect(toggle({}, odd)).toEqual({});
});

test("selected ids come out head to toe", () => {
  const sel: Selection = { accessory: bag, shoes: boots, bottom: jeans, top: tee };
  expect(selectedIds(sel)).toEqual(["tee", "jeans", "boots", "bag"]);
});

test("the total adds the known prices, like the server does", () => {
  expect(totalPrice({ top: tee, bottom: jeans })).toBe(39.98);
  expect(totalPrice({ top: product("a", "Garment Upper body", 0.1), bottom: product("b", "Garment Lower body", 0.2) })).toBe(0.3);
  expect(totalPrice({ top: tee, accessory: bag })).toBe(9.99);
  expect(totalPrice({ accessory: bag })).toBeNull();
  expect(totalPrice({})).toBeNull();
});

test("what's stopping the save, in plain words", () => {
  expect(problem({ top: tee, bottom: jeans }, "  ")).toBe("Give the set a name.");
  expect(problem({ top: tee }, "Friday")).toBe("Pick at least 2 items, one per row.");
  expect(problem({ top: tee, bottom: jeans }, "Friday")).toBeNull();
});

test("a name longer than the server accepts is caught before saving", () => {
  const sel = { top: tee, bottom: jeans };
  expect(problem(sel, "x".repeat(MAX_NAME_LENGTH))).toBeNull();
  expect(problem(sel, "x".repeat(MAX_NAME_LENGTH + 1))).toBe("Keep the name to 60 characters or fewer.");
  // Spaces around the name don't count, as on the server.
  expect(problem(sel, ` ${"x".repeat(MAX_NAME_LENGTH)} `)).toBeNull();
});

// --- Editing a saved set ---------------------------------------------------------

import type { Outfit } from "../src/api/client";
import { selectionFromOutfit, withSetItems } from "../src/outfits/builder";

const saved: Outfit = {
  id: "o1",
  name: "Friday",
  items: [
    { slot: "top", product: tee },
    { slot: "bottom", product: jeans },
    { slot: "shoes", product: boots },
  ],
  total_price: 89.97,
  currency: "GBP",
};

test("a saved set opens in the builder with its items picked", () => {
  const sel = selectionFromOutfit(saved);
  expect(selectedIds(sel)).toEqual(["tee", "jeans", "boots"]);
  expect(totalPrice(sel)).toBe(89.97);
});

test("a slot the app doesn't know is ignored rather than breaking the builder", () => {
  const odd = { ...saved, items: [...saved.items, { slot: "hat", product: bag }] };
  expect(selectedIds(selectionFromOutfit(odd))).toEqual(["tee", "jeans", "boots"]);
});

test("a set's items stay in the rows even after leaving the wardrobe", () => {
  const wardrobe = [shirt, jeans]; // tee and boots were removed from the wardrobe
  const rows = groupBySlot(withSetItems(wardrobe, saved));
  expect(rows.top.map((p) => p.id)).toEqual(["shirt", "tee"]);
  expect(rows.bottom.map((p) => p.id)).toEqual(["jeans"]); // not twice
  expect(rows.shoes.map((p) => p.id)).toEqual(["boots"]);
});
