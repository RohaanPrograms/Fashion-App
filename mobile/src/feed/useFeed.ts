// The feed screen's brain: holds the card queue, records swipes, fetches
// batches. The decisions (what to exclude, when to prefetch, when the feed
// turns personal) are the pure, tested functions in queue.ts and progress.ts;
// this hook only connects them to React state and the network.
import { Image } from "expo-image";
import { useEffect, useRef, useState } from "react";

import { api, type ApiError, type FeedItem } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { afterLike, mergeProgress, progressFrom, type Progress } from "./progress";
import {
  advance,
  appendBatch,
  currentCard,
  emptyQueue,
  excludeIds,
  excludeIdsForReplace,
  replaceUpcoming,
  shouldPrefetch,
  type FeedQueue,
} from "./queue";

// reset: start from scratch. append: the prefetch. replace: the personalised switch.
type LoadMode = "reset" | "append" | "replace";

function message(err: unknown): string {
  return (err as ApiError)?.detail ?? "Something went wrong.";
}

function prefetchPhotos(items: FeedItem[]) {
  const urls = items.map((i) => i.product.image_url).filter((u): u is string => !!u);
  if (urls.length) Image.prefetch(urls).catch(() => {}); // a missed prefetch only costs a fade-in
}

export function useFeed() {
  const { getValidToken } = useAuth();
  const [queue, setQueueState] = useState<FeedQueue>(emptyQueue);
  const [progress, setProgressState] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Refs hold the CURRENT values for async code: state captured inside an
  // async function is frozen at the moment it started.
  const queueRef = useRef(queue);
  const progressRef = useRef<Progress | null>(null);
  const appending = useRef(false);
  // Bumped by reset and replace. A reply that started before the bump is
  // stale (it would put old best-sellers back) and is ignored.
  const generation = useRef(0);
  // Swipes sent but not yet confirmed by the server.
  const pending = useRef(new Set<string>());

  function setQueue(next: FeedQueue) {
    queueRef.current = next;
    setQueueState(next);
  }
  function setProgress(next: Progress | null) {
    progressRef.current = next;
    setProgressState(next);
  }

  async function load(mode: LoadMode) {
    if (mode === "append") {
      if (appending.current) return;
      appending.current = true;
    }
    const mine = mode === "append" ? generation.current : ++generation.current;
    try {
      const token = await getValidToken();
      const q = queueRef.current;
      const exclude =
        mode === "reset" ? [] : mode === "replace" ? excludeIdsForReplace(q, pending.current) : excludeIds(q, pending.current);
      const res = await api.feed(token, exclude);
      if (mine !== generation.current) return;

      const latest = queueRef.current;
      if (mode === "reset") {
        setQueue(appendBatch(emptyQueue, res.items));
        setProgress(progressFrom(res));
      } else {
        setQueue(mode === "append" ? appendBatch(latest, res.items) : replaceUpcoming(latest, res.items));
        setProgress(mergeProgress(progressRef.current, progressFrom(res)));
      }
      prefetchPhotos(res.items.slice(0, 3));
      setError(null);
    } catch (err) {
      setError(message(err));
    } finally {
      if (mode === "append") appending.current = false;
    }
  }

  async function swipe(type: "like" | "dislike") {
    const card = currentCard(queueRef.current);
    if (!card) return;
    const id = card.product.id;
    pending.current.add(id);

    const next = advance(queueRef.current);
    setQueue(next);

    let switchNow = false;
    if (type === "like" && progressRef.current) {
      const result = afterLike(progressRef.current);
      setProgress(result.progress);
      switchNow = result.switchNow;
    }
    if (!switchNow && shouldPrefetch(next, appending.current)) void load("append");

    try {
      const token = await getValidToken();
      await api.interact(token, id, type);
    } catch (err) {
      setError(`That swipe didn't save. ${message(err)}`);
    } finally {
      pending.current.delete(id);
    }
    // Only now does the server know about the 3rd like, so only now can it
    // rank by taste.
    if (switchNow) void load("replace");
  }

  function reset() {
    setQueue(emptyQueue);
    setProgress(null);
    void load("reset");
  }

  useEffect(() => {
    void load("reset");
  }, []);

  return {
    card: currentCard(queue),
    progress,
    error,
    exhausted: queue.exhausted && currentCard(queue) === null,
    swipe,
    retry: () => void load(queue.items.length ? "append" : "reset"),
    reset,
  };
}
