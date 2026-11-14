// The words of the ⓘ panel. The numbers come straight from the server (see
// backend/app/recs/feed.py); this only turns them into sentences.
//
// What the numbers mean: the model learned 128 numbers for every garment
// from who bought what. Your taste is the average of the numbers of what
// you've liked. The "match score" is the cosine similarity between a card's
// numbers and your taste: 1 means they point the same way, 0 unrelated.

import type { Product, Reason } from "../api/client";

export type Explanation = { headline: string; detail: string };

export function formatSimilarity(s: number): string {
  return s.toFixed(2);
}

function score(similarity: number | null): string {
  return similarity === null
    ? ""
    : ` Match score ${formatSimilarity(similarity)} (1.00 would be exactly your taste).`;
}

export function explainReason(reason: Reason, likesNeeded: number): Explanation {
  switch (reason.kind) {
    case "popular":
      return {
        headline: "A best-seller",
        detail:
          likesNeeded > 0
            ? `The model doesn't know your taste yet, so this is one of the catalogue's most-bought pieces. ` +
              `Like ${likesNeeded} more ${likesNeeded === 1 ? "item" : "items"} and the feed switches to your style.`
            : "One of the catalogue's most-bought pieces.",
      };
    case "similar":
      return {
        headline: reason.because_of ? `Because you liked ${reason.because_of.name}` : "Close to your taste",
        detail:
          "The model learned 128 numbers for every garment from real purchases. " +
          "This one's numbers sit close to the average of what you've liked." +
          score(reason.similarity),
      };
    case "explore":
      return {
        headline: "A wildcard",
        detail:
          "Picked at random from your top 100 matches, so the feed doesn't narrow to one lane." +
          score(reason.similarity) +
          (reason.because_of ? ` Closest to ${reason.because_of.name}.` : ""),
      };
  }
}

/** "About this piece": "Vest top · Black · Solid", then H&M's description. */
export function aboutPiece(product: Product): { facts: string; description: string | null } {
  return {
    facts: [product.type, product.colour, product.pattern].filter(Boolean).join(" · "),
    description: product.description,
  };
}
