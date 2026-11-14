// "Start over" happens on the Wardrobe tab, but the cards live on the Feed
// tab, which stays alive in the background. This tiny counter goes up on
// every start-over; the feed watches it and reloads when it changes.
import { useSyncExternalStore } from "react";

let version = 0;
const listeners = new Set<() => void>();

export function bumpFeedReset() {
  version += 1;
  listeners.forEach((listener) => listener());
}

export function currentResetVersion(): number {
  return version;
}

export function subscribeToReset(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useFeedResetVersion(): number {
  return useSyncExternalStore(subscribeToReset, currentResetVersion);
}
