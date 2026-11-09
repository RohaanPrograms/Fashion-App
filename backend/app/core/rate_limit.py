"""A small in-memory rate limiter, and how to find the caller's IP address.

Used to cap how many guest accounts one network can create per hour. Guest
accounts cost nothing to make, so without a cap one script could fill the
database and use up Supabase's hourly sign-in allowance for everyone.

LIMITS OF THIS APPROACH
-----------------------
- The counts live in this process's memory: a restart forgets them, and two
  server processes would each count separately. Fine for one demo server.
- An IP address is a stand-in for "one person". An office shares one; a
  determined abuser can switch networks. The goal is to make abuse tedious,
  not impossible.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

from starlette.requests import Request

# Above this many tracked addresses, sweep out the ones with nothing recent,
# so addresses that never come back do not accumulate forever.
_SWEEP_ABOVE = 10_000


class RateLimiter:
    """At most `limit` events per key within any `window_seconds` (a sliding window)."""

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        # Endpoints run on several threads at once; without the lock two
        # requests could both see "4 so far" and both be let through.
        self._lock = threading.Lock()

    def hit(self, key: str) -> float | None:
        """Record an event for `key` if allowed.

        Returns None when allowed, or the seconds until the next one would be.
        A refused attempt is not recorded, so retrying does not push the wait back.
        """
        with self._lock:
            now = self._clock()
            if len(self._events) > _SWEEP_ABOVE:
                self._sweep(now)
            events = self._events.setdefault(key, deque())
            self._forget_old(events, now)
            if len(events) >= self._limit:
                return events[0] + self._window - now
            events.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def _forget_old(self, events: deque[float], now: float) -> None:
        while events and now - events[0] >= self._window:
            events.popleft()

    def _sweep(self, now: float) -> None:
        for key in list(self._events):
            self._forget_old(self._events[key], now)
            if not self._events[key]:
                del self._events[key]


def client_ip(request: Request) -> str:
    """The caller's IP address.

    In production the server sits behind Railway's proxy, so the connection
    comes from the proxy, not the visitor. The proxy records the visitor's
    address in X-Forwarded-For, ADDING it to the end of whatever the request
    already carried. Entries before it came from the visitor and may be made
    up, so only the last one is trusted.

    With no proxy (local development) the header is normally absent and the
    connection's own address is used.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"
