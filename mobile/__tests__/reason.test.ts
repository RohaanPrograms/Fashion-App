// The ⓘ panel's words: what the garment is, and why the model showed it.
import type { Product, Reason } from "../src/api/client";
import { aboutPiece, explainReason, formatSimilarity } from "../src/feed/reason";

const popular: Reason = { kind: "popular", similarity: null, because_of: null };
const similar: Reason = { kind: "similar", similarity: 0.5234, because_of: { id: "1", name: "Black hoodie" } };
const explore: Reason = { kind: "explore", similarity: 0.211, because_of: { id: "2", name: "Denim jacket" } };

const prima: Product = {
  id: "p",
  name: "Prima",
  brand: "H&M",
  price: 17.14,
  currency: "GBP",
  image_url: null,
  category: "Garment Upper body",
  colour: "Black",
  type: "Vest top",
  pattern: "Solid",
  description: "V-neck top in woven fabric with spaghetti shoulder straps.",
};

test("similarity is shown with two decimals", () => {
  expect(formatSimilarity(0.5234)).toBe("0.52");
  expect(formatSimilarity(1)).toBe("1.00");
});

test("a best-seller says how many likes are still needed", () => {
  const { headline, detail } = explainReason(popular, 2);
  expect(headline).toBe("A best-seller");
  expect(detail).toContain("Like 2 more items");
});

test("one like left is singular", () => {
  expect(explainReason(popular, 1).detail).toContain("Like 1 more item ");
});

test("a similar card names the liked item and the score", () => {
  const { headline, detail } = explainReason(similar, 0);
  expect(headline).toBe("Because you liked Black hoodie");
  expect(detail).toContain("0.52");
});

test("a similar card without a nearest item still explains itself", () => {
  const { headline } = explainReason({ ...similar, because_of: null }, 0);
  expect(headline).toBe("Close to your taste");
});

test("an exploration card says it is a wildcard", () => {
  const { headline, detail } = explainReason(explore, 0);
  expect(headline).toBe("A wildcard");
  expect(detail).toContain("top 100");
  expect(detail).toContain("0.21");
  expect(detail).toContain("Denim jacket");
});

test("about this piece: type, colour and pattern, then the description", () => {
  expect(aboutPiece(prima)).toEqual({
    facts: "Vest top · Black · Solid",
    description: "V-neck top in woven fabric with spaghetti shoulder straps.",
  });
});

test("missing details are left out rather than shown as blanks", () => {
  const bare = { ...prima, type: null, pattern: null, description: null };
  expect(aboutPiece(bare)).toEqual({ facts: "Black", description: null });
});
