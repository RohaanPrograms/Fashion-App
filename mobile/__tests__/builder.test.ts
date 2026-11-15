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

function product(id: string, category: string | null, price: number | null = 10, type: string | null = null): Product {
  return {
    id,
    name: id,
    brand: null,
    price,
    currency: "USD",
    image_url: null,
    category,
    colour: null,
    type,
    pattern: null,
    description: null,
    colour_family: null,
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

test("a dress removes the bottom, but a top can stay under it", () => {
  const sel = toggle(toggle(toggle(toggle({}, tee), jeans), boots), dress);
  expect(selectedIds(sel)).toEqual(["tee", "dress", "boots"]);
});

test("a bottom removes the dress", () => {
  const sel = toggle(toggle({}, dress), jeans);
  expect(selectedIds(sel)).toEqual(["jeans"]);
});

test("items that can't go in a set are ignored", () => {
  expect(toggle({}, odd)).toEqual({});
});

test("selected ids come out head to toe", () => {
  const sel: Selection = { accessory: [bag], shoes: boots, bottom: jeans, top: tee };
  expect(selectedIds(sel)).toEqual(["tee", "jeans", "boots", "bag"]);
});

test("the total adds the known prices, like the server does", () => {
  expect(totalPrice({ top: tee, bottom: jeans })).toBe(39.98);
  expect(totalPrice({ top: product("a", "Garment Upper body", 0.1), bottom: product("b", "Garment Lower body", 0.2) })).toBe(0.3);
  expect(totalPrice({ top: tee, accessory: [bag] })).toBe(9.99);
  expect(totalPrice({ accessory: [bag] })).toBeNull();
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

test("an item filed under a row the app doesn't know goes back in its own row", () => {
  const strange = { ...saved, items: [...saved.items, { slot: "hat", product: bag }] };
  expect(selectedIds(selectionFromOutfit(strange))).toEqual(["tee", "jeans", "boots", "bag"]);
});

test("an item that can't go in any row is skipped rather than breaking the builder", () => {
  const withOdd = { ...saved, items: [...saved.items, { slot: "hat", product: odd }] };
  expect(selectedIds(selectionFromOutfit(withOdd))).toEqual(["tee", "jeans", "boots"]);
});

test("a set's items stay in the rows even after leaving the wardrobe", () => {
  const wardrobe = [shirt, jeans]; // tee and boots were removed from the wardrobe
  const rows = groupBySlot(withSetItems(wardrobe, saved));
  expect(rows.top.map((p) => p.id)).toEqual(["shirt", "tee"]);
  expect(rows.bottom.map((p) => p.id)).toEqual(["jeans"]); // not twice
  expect(rows.shoes.map((p) => p.id)).toEqual(["boots"]);
});


// --- Layering ---------------------------------------------------------------------

import { SLOT_ORDER, selectedSlots, slotsOf } from "../src/outfits/builder";

const tank = product("tank", "Garment Upper body", 7, "Vest top");
const jacket = product("jacket", "Garment Upper body", 40, "Jacket");
const cardigan = product("cardigan", "Garment Upper body", 25, "Cardigan");
const jumper = product("jumper", "Garment Upper body", 20, "Sweater");
const openShirt = product("openShirt", "Garment Upper body", 18, "Shirt");

test("the rows run head to toe, with Layer over whatever is under it", () => {
  expect(SLOT_ORDER).toEqual(["top", "full_body", "layer", "bottom", "shoes", "accessory"]);
});

test("each garment type goes in its rows", () => {
  expect(slotsOf(tank)).toEqual(["top"]);
  expect(slotsOf(jacket)).toEqual(["layer"]);
  expect(slotsOf(jumper)).toEqual(["layer", "top"]);
  expect(slotsOf(openShirt)).toEqual(["top", "layer"]);
  expect(slotsOf(odd)).toEqual([]);
});

test("a jumper or shirt is offered in both the Top and Layer rows", () => {
  const rows = groupBySlot([tank, jumper, jacket]);
  expect(rows.top.map((p) => p.id)).toEqual(["tank", "jumper"]);
  expect(rows.layer.map((p) => p.id)).toEqual(["jumper", "jacket"]);
});

test("a tee under a jacket, and a tank under a dress with a cardigan over it", () => {
  expect(selectedIds(toggle(toggle({}, tee), jacket))).toEqual(["tee", "jacket"]);
  const dressy = toggle(toggle(toggle({}, tank), dress), cardigan);
  expect(selectedIds(dressy)).toEqual(["tank", "dress", "cardigan"]);
});

test("a second layer replaces the first", () => {
  expect(toggle(toggle({}, jacket), cardigan).layer?.id).toBe("cardigan");
});

test("you choose the row a jumper goes in, and it can't be in both", () => {
  const asTop = toggle({}, jumper, "top");
  expect(asTop.top?.id).toBe("jumper");
  const moved = toggle(asTop, jumper, "layer");
  expect(moved.layer?.id).toBe("jumper");
  expect(moved.top).toBeUndefined();
});

test("a garment can't be put in a row it doesn't belong in", () => {
  expect(toggle({}, jacket, "top")).toEqual({});
});

test("the role of each picked item is sent with it, head to toe", () => {
  const sel = toggle(toggle(toggle({}, tank), openShirt, "layer"), jeans);
  expect(selectedIds(sel)).toEqual(["tank", "openShirt", "jeans"]);
  expect(selectedSlots(sel)).toEqual(["top", "layer", "bottom"]);
});

test("a saved set with a layer opens with it in the Layer row", () => {
  const saved: Outfit = {
    id: "o2", name: "Layers", total_price: null, currency: "GBP",
    items: [{ slot: "top", product: tee }, { slot: "layer", product: jumper }],
  };
  const sel = selectionFromOutfit(saved);
  expect(sel.layer?.id).toBe("jumper");
  expect(selectedSlots(sel)).toEqual(["top", "layer"]);
});


test("an old set with a jacket filed as a top opens with it in the Layer row", () => {
  const old: Outfit = {
    id: "o3", name: "Before layering", total_price: null, currency: "GBP",
    items: [{ slot: "top", product: jacket }, { slot: "bottom", product: jeans }],
  };
  const sel = selectionFromOutfit(old);
  expect(sel.layer?.id).toBe("jacket");
  expect(sel.top).toBeUndefined();
  expect(selectedSlots(sel)).toEqual(["layer", "bottom"]);
});


// --- Several accessories -----------------------------------------------------------
// One bag, one hat, one pair of sunglasses, one belt, one scarf; as much
// jewellery and as many hair accessories as you like.

import { isPicked, rowHasPick } from "../src/outfits/builder";

const acc = (id: string, type: string) => product(id, "Accessories", 5, type);
const necklace = acc("necklace", "Necklace");
const ring = acc("ring", "Ring");
const earrings = acc("earrings", "Earring");
const tote = acc("tote", "Bag");
const purse = acc("purse", "Bag");
const cap = acc("cap", "Cap/peaked");
const shades = acc("shades", "Sunglasses");
const clip = acc("clip", "Hair clip");
const band = acc("band", "Hair/alice band");

test("jewellery stacks: necklace, ring and earrings together", () => {
  const sel = toggle(toggle(toggle(toggle({}, tee), necklace), ring), earrings);
  expect(selectedIds(sel)).toEqual(["tee", "necklace", "ring", "earrings"]);
  expect(selectedSlots(sel)).toEqual(["top", "accessory", "accessory", "accessory"]);
});

test("hair accessories stack too", () => {
  expect(selectedIds(toggle(toggle({}, clip), band))).toEqual(["clip", "band"]);
});

test("a second bag replaces the first, and leaves the jewellery alone", () => {
  const sel = toggle(toggle(toggle({}, tote), necklace), purse);
  expect(selectedIds(sel)).toEqual(["necklace", "purse"]);
});

test("a bag, a hat, sunglasses and jewellery can all go together", () => {
  const sel = [tote, cap, shades, necklace, ring].reduce((s: Selection, p) => toggle(s, p), {});
  expect(selectedIds(sel)).toEqual(["tote", "cap", "shades", "necklace", "ring"]);
});

test("tapping a picked accessory again removes just that one", () => {
  const sel = toggle(toggle(toggle({}, necklace), ring), necklace);
  expect(selectedIds(sel)).toEqual(["ring"]);
});

test("the builder can ask whether a tile, or a row, is picked", () => {
  const sel = toggle(toggle({}, tee), ring);
  expect(isPicked(sel, "accessory", ring)).toBe(true);
  expect(isPicked(sel, "accessory", necklace)).toBe(false);
  expect(isPicked(sel, "top", tee)).toBe(true);
  expect(rowHasPick(sel, "accessory")).toBe(true);
  expect(rowHasPick(sel, "shoes")).toBe(false);
  expect(rowHasPick(toggle(sel, ring), "accessory")).toBe(false); // an emptied list is no pick
});

test("a saved set with several accessories opens with all of them picked", () => {
  const saved: Outfit = {
    id: "o4", name: "Jewels", total_price: null, currency: "GBP",
    items: [
      { slot: "top", product: tee },
      { slot: "accessory", product: necklace },
      { slot: "accessory", product: ring },
      { slot: "accessory", product: tote },
    ],
  };
  expect(selectedIds(selectionFromOutfit(saved))).toEqual(["tee", "necklace", "ring", "tote"]);
});

// --- Picked first, and the review page ----------------------------------------------

import { orderRow, reviewGroups } from "../src/outfits/builder";

const ids2 = (ps: Product[]) => ps.map((p) => p.id);

test("a picked item moves to the front of its row; the rest keep their order", () => {
  const row = [tee, shirt, tank];
  expect(ids2(orderRow(row, toggle({}, tank), "top"))).toEqual(["tank", "tee", "shirt"]);
});

test("unpicking puts it back where it was", () => {
  const row = [tee, shirt, tank];
  const sel = toggle(toggle({}, tank), tank);
  expect(ids2(orderRow(row, sel, "top"))).toEqual(["tee", "shirt", "tank"]);
});

test("several accessories line up at the front in the order picked", () => {
  const row = [tote, necklace, cap, ring, earrings];
  const sel = toggle(toggle(toggle({}, ring), tote), necklace);
  expect(ids2(orderRow(row, sel, "accessory"))).toEqual(["ring", "tote", "necklace", "cap", "earrings"]);
});

test("picking in one row doesn't reorder another", () => {
  const row = [tee, shirt, tank];
  expect(ids2(orderRow(row, toggle({}, jeans), "top"))).toEqual(["tee", "shirt", "tank"]);
});

test("a jumper picked as a Layer is first in Layer but stays in place in Top", () => {
  const sel = toggle({}, jumper, "layer");
  expect(ids2(orderRow([jacket, jumper], sel, "layer"))).toEqual(["jumper", "jacket"]);
  expect(ids2(orderRow([tee, jumper], sel, "top"))).toEqual(["tee", "jumper"]);
});

test("the review groups the picks head to toe, leaving out empty rows", () => {
  const sel = [necklace, jeans, tee, ring, jacket].reduce((s: Selection, p) => toggle(s, p), {});
  expect(reviewGroups(sel).map((g) => [g.label, ids2(g.items)])).toEqual([
    ["Top", ["tee"]],
    ["Layer", ["jacket"]],
    ["Bottom", ["jeans"]],
    ["Accessories", ["necklace", "ring"]],
  ]);
});

test("one accessory is labelled in the singular", () => {
  expect(reviewGroups(toggle({}, tote)).map((g) => g.label)).toEqual(["Accessory"]);
});
