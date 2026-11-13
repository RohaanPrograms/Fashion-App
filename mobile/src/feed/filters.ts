// The filter buttons above the feed, as pure functions.
//
// Row 1: All · Tops · Bottoms · Dresses · Shoes · Accessories
//   Tapping a category OPENS it (shows row 2); it doesn't change the feed.
// Row 2: All tops · T-shirts · Blouses · …
//   Each button is an on/off switch. Several can be on, across categories:
//   T-shirts + Sunglasses. The feed then takes turns between them.
//
// A "pick" is what the server is sent: "tops" (the whole category) or
// "tops:t-shirts". The list of buttons comes from the server
// (GET /v1/feed/filters), so these functions are handed it.

import type { CategoryOption } from "../api/client";

export type Picks = string[];

export const NO_PICKS: Picks = [];

function categoryOf(pick: string): string {
  return pick.split(":")[0];
}

/** Turn one button on or off. "All tops" and a single top type exclude each
 *  other: picking one replaces the other, so the request means what it shows. */
export function togglePick(picks: Picks, pick: string): Picks {
  if (picks.includes(pick)) return picks.filter((p) => p !== pick);
  const category = categoryOf(pick);
  const whole = !pick.includes(":");
  const kept = picks.filter((p) =>
    categoryOf(p) !== category ? true : whole ? false : p.includes(":")
  );
  return [...kept, pick];
}

/** How many picks are on in this category: the number on its row-1 button. */
export function picksIn(picks: Picks, category: string): number {
  return picks.filter((p) => categoryOf(p) === category).length;
}

export function samePicks(a: Picks, b: Picks): boolean {
  return a.length === b.length && a.every((p, i) => p === b[i]);
}

/** The query-string part for GET /v1/feed: "&pick=tops%3At-shirts&pick=shoes". */
export function filterQuery(picks: Picks): string {
  return picks.map((p) => `&pick=${encodeURIComponent(p)}`).join("");
}

/** A pick in words: "T-shirts", or "Tops" for a whole category. */
export function pickLabel(pick: string, options: CategoryOption[]): string {
  const [categoryKey, typeKey] = pick.split(":");
  const category = options.find((c) => c.key === categoryKey);
  if (!category) return pick;
  if (!typeKey) return category.label;
  return category.types.find((t) => t.key === typeKey)?.label ?? pick;
}

/** "T-shirts", "T-shirts and Sunglasses", "T-shirts, Boots and Sunglasses". */
export function picksSummary(picks: Picks, options: CategoryOption[]): string {
  const names = picks.map((p) => pickLabel(p, options));
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

export function exhaustedMessage(picks: Picks, options: CategoryOption[]): string {
  if (picks.length === 0) return "You've seen the whole catalogue. Start over from the Wardrobe tab.";
  return `You've seen all the ${picksSummary(picks, options).toLowerCase()}. Change the filter, or pick All.`;
}
