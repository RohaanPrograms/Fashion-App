// The feed's card queue: which card is on screen, when to fetch the next
// batch (card 7 of 10), and which ids to tell the server to skip, so a card
// never shows twice.
import type { FeedItem } from "../src/api/client";
import {
  MAX_EXCLUDE,
  advance,
  appendBatch,
  cardsLeft,
  currentCard,
  emptyQueue,
  excludeIds,
  excludeIdsForReplace,
  replaceUpcoming,
  shouldPrefetch,
  type FeedQueue,
} from "../src/feed/queue";

function card(id: string): FeedItem {
  return {
    product: { id, name: id, brand: null, price: null, currency: "USD", image_url: null, category: null, colour: null, type: null, pattern: null, description: null },
    reason: { kind: "popular", similarity: null, because_of: null },
  };
}
const batch = (...ids: string[]) => ids.map(card);
const ids = (q: FeedQueue) => q.items.map((i) => i.product.id);
const ten = batch("c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10");
const at = (position: number): FeedQueue => ({ ...appendBatch(emptyQueue, ten), position });

test("a new queue shows the first card of the batch", () => {
  const q = appendBatch(emptyQueue, ten);
  expect(currentCard(q)?.product.id).toBe("c1");
  expect(cardsLeft(q)).toBe(10);
});

test("advance moves to the next card and stops at the end", () => {
  expect(currentCard(advance(at(0)))?.product.id).toBe("c2");
  expect(currentCard(advance(at(9)))).toBeNull();
  expect(advance(advance(at(9))).position).toBe(10);
});

test("prefetch starts on card 7 of 10, not before", () => {
  for (let position = 0; position < 6; position++) {
    expect(shouldPrefetch(at(position), false)).toBe(false);
  }
  expect(shouldPrefetch(at(6), false)).toBe(true); // card 7
});

test("no second prefetch while one is loading, and none once the catalogue is exhausted", () => {
  expect(shouldPrefetch(at(6), true)).toBe(false);
  expect(shouldPrefetch({ ...at(6), exhausted: true }, false)).toBe(false);
});

test("an empty queue wants cards", () => {
  expect(shouldPrefetch(emptyQueue, false)).toBe(true);
});

test("the prefetch excludes the card on screen, the ones waiting, and unsaved swipes", () => {
  expect(excludeIds(at(6), ["c6"])).toEqual(["c7", "c8", "c9", "c10", "c6"]);
});

test("exclusions have no duplicates and never exceed the server's limit of 50", () => {
  expect(excludeIds(at(6), ["c7"])).toEqual(["c7", "c8", "c9", "c10"]);
  const many = appendBatch(emptyQueue, batch(...Array.from({ length: 60 }, (_, i) => `x${i}`)));
  expect(excludeIds(many, [])).toHaveLength(MAX_EXCLUDE);
});

test("the replacement fetch excludes only the card on screen and unsaved swipes", () => {
  expect(excludeIdsForReplace(at(3), ["c3"])).toEqual(["c4", "c3"]);
});

test("a batch is appended without any card already in the queue", () => {
  const q = appendBatch(at(6), batch("c9", "n1", "c2", "n2"));
  expect(ids(q).slice(10)).toEqual(["n1", "n2"]);
  expect(q.position).toBe(6);
  expect(q.exhausted).toBe(false);
});

test("a batch with nothing new means the catalogue is exhausted", () => {
  expect(appendBatch(at(9), []).exhausted).toBe(true);
  expect(appendBatch(at(9), batch("c10")).exhausted).toBe(true);
});

test("replaceUpcoming keeps what was seen and the card on screen, swaps the rest", () => {
  const q = replaceUpcoming(at(3), batch("p1", "c4", "p2"));
  expect(ids(q)).toEqual(["c1", "c2", "c3", "c4", "p1", "p2"]);
  expect(q.position).toBe(3);
  expect(currentCard(q)?.product.id).toBe("c4");
});
