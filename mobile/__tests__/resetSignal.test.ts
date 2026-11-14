// "Start over" on the Wardrobe tab must reach the Feed tab: every bump is
// heard by whoever is listening, and a listener that has left hears nothing.
import { bumpFeedReset, currentResetVersion, subscribeToReset } from "../src/feed/resetSignal";

test("a start-over is heard by the feed, once per bump", () => {
  const heard = jest.fn();
  const before = currentResetVersion();
  const stop = subscribeToReset(heard);

  bumpFeedReset();
  expect(heard).toHaveBeenCalledTimes(1);
  expect(currentResetVersion()).toBe(before + 1);

  stop();
  bumpFeedReset();
  expect(heard).toHaveBeenCalledTimes(1);
});
