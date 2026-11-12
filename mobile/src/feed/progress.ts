// How far the visitor is from a personalised feed. Below 3 likes the server
// ranks by best-sellers; from the 3rd like on, by similarity to their taste.
// The app counts likes itself so it can switch the moment the 3rd one is
// saved, rather than waiting for the next batch at card 11.

import type { FeedResponse } from "../api/client";

export type Progress = { personalised: boolean; likes: number; likesNeeded: number };

export function progressFrom(res: FeedResponse): Progress {
  return { personalised: res.personalised, likes: res.likes, likesNeeded: res.likes_needed };
}

/** A reply fetched before the latest likes were saved must not undo them. */
export function mergeProgress(local: Progress | null, server: Progress): Progress {
  if (!local || server.likes >= local.likes) return server;
  return local;
}

export function afterLike(p: Progress): { progress: Progress; switchNow: boolean } {
  if (p.personalised) {
    return { progress: { ...p, likes: p.likes + 1 }, switchNow: false };
  }
  const likesNeeded = Math.max(0, p.likesNeeded - 1);
  const personalised = likesNeeded === 0;
  return {
    progress: { personalised, likes: p.likes + 1, likesNeeded },
    switchNow: personalised,
  };
}

export function progressLabel(p: Progress | null): string {
  if (!p) return "";
  if (p.personalised) return `Personalised from your ${p.likes} ${p.likes === 1 ? "like" : "likes"}`;
  return `Best-sellers for now · like ${p.likesNeeded} more to personalise`;
}
