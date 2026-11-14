// Try once more when a request fails for a reason that usually fixes itself.
//
// "Transient" means the request never got a real answer: the network dropped
// (status 0), or the server couldn't reach the database just then (503, or a
// gateway error in front of it: 502, 504). A dropped connection is almost
// always fine on the second try. A real "no" (400, 401, 404…) is not retried:
// asking again would get the same answer.

import type { ApiError } from "./client";

const TRANSIENT_STATUSES = new Set([0, 502, 503, 504]);
export const RETRY_DELAY_MS = 1000;

export function isTransient(err: unknown): boolean {
  const status = (err as ApiError)?.status;
  return typeof status === "number" && TRANSIENT_STATUSES.has(status);
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Run `attempt`; if it fails transiently, wait and run it once more. */
export async function withOneRetry<T>(
  attempt: () => Promise<T>,
  wait: (ms: number) => Promise<void> = sleep // replaced in tests, so they don't really wait
): Promise<T> {
  try {
    return await attempt();
  } catch (err) {
    if (!isTransient(err)) throw err;
    await wait(RETRY_DELAY_MS);
    return attempt();
  }
}
