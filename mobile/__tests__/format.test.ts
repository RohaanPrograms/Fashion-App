// Prices on the cards: the right currency sign, and never a misleading "$0.00".
import { formatPrice } from "../src/format";

test("prices are shown in their currency", () => {
  expect(formatPrice(12.5, "USD")).toBe("$12.50");
});

test("a missing price says so instead of showing 0", () => {
  expect(formatPrice(null, "USD")).toBe("Price unknown");
});

test("an unknown currency code still shows the number", () => {
  expect(formatPrice(12.5, "NOPE")).toBe("12.50 NOPE");
});
