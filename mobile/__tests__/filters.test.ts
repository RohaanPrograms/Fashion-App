// The filter buttons: what each tap turns on or off, what the server is
// asked for, and what the screen says about it.
import type { CategoryOption } from "../src/api/client";
import {
  NO_PICKS,
  exhaustedMessage,
  filterQuery,
  pickLabel,
  picksIn,
  picksSummary,
  samePicks,
  togglePick,
} from "../src/feed/filters";

const options: CategoryOption[] = [
  { key: "tops", label: "Tops", types: [{ key: "t-shirts", label: "T-shirts" }, { key: "blouses", label: "Blouses" }] },
  { key: "shoes", label: "Shoes", types: [{ key: "boots", label: "Boots" }] },
  { key: "accessories", label: "Accessories", types: [{ key: "sunglasses", label: "Sunglasses" }] },
];

test("buttons switch on and off", () => {
  const on = togglePick(NO_PICKS, "tops:t-shirts");
  expect(on).toEqual(["tops:t-shirts"]);
  expect(togglePick(on, "tops:t-shirts")).toEqual([]);
});

test("several types can be on, across categories", () => {
  let picks = togglePick(NO_PICKS, "tops:t-shirts");
  picks = togglePick(picks, "accessories:sunglasses");
  picks = togglePick(picks, "tops:blouses");
  expect(picks).toEqual(["tops:t-shirts", "accessories:sunglasses", "tops:blouses"]);
});

test("'All tops' replaces single top types, and a single type replaces 'All tops'", () => {
  const types = ["tops:t-shirts", "tops:blouses", "shoes:boots"];
  const whole = togglePick(types, "tops");
  expect(whole).toEqual(["shoes:boots", "tops"]);
  expect(togglePick(whole, "tops:t-shirts")).toEqual(["shoes:boots", "tops:t-shirts"]);
});

test("each category button counts its picks", () => {
  const picks = ["tops:t-shirts", "tops:blouses", "shoes"];
  expect(picksIn(picks, "tops")).toBe(2);
  expect(picksIn(picks, "shoes")).toBe(1);
  expect(picksIn(picks, "accessories")).toBe(0);
});

test("samePicks compares in order", () => {
  expect(samePicks(["tops"], ["tops"])).toBe(true);
  expect(samePicks(["tops", "shoes"], ["shoes", "tops"])).toBe(false);
  expect(samePicks([], [])).toBe(true);
});

test("the server is asked for exactly the picks on screen", () => {
  expect(filterQuery(NO_PICKS)).toBe("");
  expect(filterQuery(["tops:t-shirts", "shoes"])).toBe("&pick=tops%3At-shirts&pick=shoes");
});

test("picks are named in words", () => {
  expect(pickLabel("tops", options)).toBe("Tops");
  expect(pickLabel("accessories:sunglasses", options)).toBe("Sunglasses");
  expect(picksSummary(["tops:t-shirts"], options)).toBe("T-shirts");
  expect(picksSummary(["tops:t-shirts", "accessories:sunglasses"], options)).toBe("T-shirts and Sunglasses");
  expect(picksSummary(["tops:t-shirts", "shoes:boots", "accessories:sunglasses"], options)).toBe(
    "T-shirts, Boots and Sunglasses"
  );
});

test("running out says what ran out", () => {
  expect(exhaustedMessage(NO_PICKS, options)).toMatch(/whole catalogue/);
  expect(exhaustedMessage(["shoes:boots", "accessories:sunglasses"], options)).toBe(
    "You've seen all the boots and sunglasses. Change the filter, or pick All."
  );
});
