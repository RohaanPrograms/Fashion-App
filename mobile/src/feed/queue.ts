// The feed's card queue, as pure functions: no React, no network.
//
// The server sends cards in batches of 10. The screen shows one at a time and,
// at card 7 of 10, asks for the next batch so it's ready before the queue runs
// dry (a "prefetch"). Two rules stop the prefetch from showing a card twice:
//   * it sends ?exclude= with every card the server can't know we already
//     have: the one on screen, the ones waiting, and swipes still being saved;
//   * anything that arrives anyway is dropped (appendBatch removes duplicates).

import type { FeedItem } from "../api/client";

/** Prefetch when this many cards are left, counting the one on screen: card 7 of 10. */
export const PREFETCH_WHEN_LEFT = 4;
/** The server accepts at most 50 ids in ?exclude=. */
export const MAX_EXCLUDE = 50;

export type FeedQueue = {
  items: FeedItem[]; // every card received, in order
  position: number; // index of the card on screen
  exhausted: boolean; // the last fetch brought nothing new
};

export const emptyQueue: FeedQueue = { items: [], position: 0, exhausted: false };

export function currentCard(q: FeedQueue): FeedItem | null {
  return q.items[q.position] ?? null;
}

export function cardsLeft(q: FeedQueue): number {
  return q.items.length - q.position;
}

export function advance(q: FeedQueue): FeedQueue {
  return { ...q, position: Math.min(q.position + 1, q.items.length) };
}

export function shouldPrefetch(q: FeedQueue, alreadyLoading: boolean): boolean {
  return !alreadyLoading && !q.exhausted && cardsLeft(q) <= PREFETCH_WHEN_LEFT;
}

function uniqueCapped(first: Iterable<string>, then: Iterable<string>): string[] {
  const out = new Set<string>(first);
  for (const id of then) out.add(id);
  return [...out].slice(0, MAX_EXCLUDE);
}

/** For a prefetch: the card on screen, the cards waiting, and unsaved swipes. */
export function excludeIds(q: FeedQueue, pending: Iterable<string>): string[] {
  return uniqueCapped(
    q.items.slice(q.position).map((i) => i.product.id),
    pending
  );
}

/** For the personalised switch: only the card on screen and unsaved swipes. The
 *  waiting best-sellers are being replaced, so they may come back if they rank. */
export function excludeIdsForReplace(q: FeedQueue, pending: Iterable<string>): string[] {
  const onScreen = currentCard(q);
  return uniqueCapped(onScreen ? [onScreen.product.id] : [], pending);
}

function withoutKnown(known: FeedItem[], batch: FeedItem[]): FeedItem[] {
  const seen = new Set(known.map((i) => i.product.id));
  return batch.filter((i) => !seen.has(i.product.id));
}

export function appendBatch(q: FeedQueue, batch: FeedItem[]): FeedQueue {
  const fresh = withoutKnown(q.items, batch);
  return { items: [...q.items, ...fresh], position: q.position, exhausted: fresh.length === 0 };
}

/** Keep everything seen and the card on screen; swap the cards still waiting. */
export function replaceUpcoming(q: FeedQueue, batch: FeedItem[]): FeedQueue {
  const kept = q.items.slice(0, q.position + 1);
  const fresh = withoutKnown(kept, batch);
  return { items: [...kept, ...fresh], position: q.position, exhausted: fresh.length === 0 };
}
