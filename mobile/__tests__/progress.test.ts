// How far the visitor is from a personalised feed (3 likes), and making sure
// the switch happens the moment the 3rd like is saved, exactly once.
import type { FeedResponse } from "../src/api/client";
import { afterLike, mergeProgress, progressFrom, progressLabel } from "../src/feed/progress";

const cold = { personalised: false, likes: 0, likesNeeded: 3 };

test("progressFrom works out how many likes are left (the server sends the total)", () => {
  const res: FeedResponse = { personalised: false, likes: 1, likes_needed: 3, items: [] };
  expect(progressFrom(res)).toEqual({ personalised: false, likes: 1, likesNeeded: 2 });
});

test("a guest who reloads with 2 likes is told 1 more, not 3", () => {
  const res: FeedResponse = { personalised: false, likes: 2, likes_needed: 3, items: [] };
  expect(progressLabel(progressFrom(res))).toBe("Best-sellers for now · like 1 more to personalise");
});

test("a personalised feed needs no more likes", () => {
  const res: FeedResponse = { personalised: true, likes: 7, likes_needed: 3, items: [] };
  expect(progressFrom(res)).toEqual({ personalised: true, likes: 7, likesNeeded: 0 });
});

test("the third like switches the feed, exactly once", () => {
  const one = afterLike(cold);
  const two = afterLike(one.progress);
  const three = afterLike(two.progress);
  const four = afterLike(three.progress);

  expect([one.switchNow, two.switchNow, three.switchNow, four.switchNow]).toEqual([false, false, true, false]);
  expect(three.progress).toEqual({ personalised: true, likes: 3, likesNeeded: 0 });
  expect(four.progress.likes).toBe(4);
});

test("a late server reply never moves the count backwards", () => {
  const local = { personalised: false, likes: 2, likesNeeded: 1 };
  const staleServer = { personalised: false, likes: 1, likesNeeded: 2 };
  expect(mergeProgress(local, staleServer)).toEqual(local);
});

test("a newer server reply wins", () => {
  const local = { personalised: false, likes: 2, likesNeeded: 1 };
  const server = { personalised: true, likes: 3, likesNeeded: 0 };
  expect(mergeProgress(local, server)).toEqual(server);
  expect(mergeProgress(null, server)).toEqual(server);
});

test.each([
  [null, ""],
  [{ personalised: false, likes: 0, likesNeeded: 3 }, "Best-sellers for now · like 3 more to personalise"],
  [{ personalised: false, likes: 2, likesNeeded: 1 }, "Best-sellers for now · like 1 more to personalise"],
  [{ personalised: true, likes: 1, likesNeeded: 0 }, "Personalised from your 1 like"],
  [{ personalised: true, likes: 5, likesNeeded: 0 }, "Personalised from your 5 likes"],
])("progressLabel(%j)", (progress, label) => {
  expect(progressLabel(progress)).toBe(label);
});
