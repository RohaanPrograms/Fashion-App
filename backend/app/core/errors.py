"""Telling "the service is down" apart from "your credentials are wrong".

Why this exists
---------------
Every auth endpoint used to wrap its Supabase call in `except Exception` and
report the result as 401 "Invalid email or password". That is right for a
rejected password and badly wrong for an outage: when the Supabase project was
paused, a user with correct credentials was told their password was wrong, and
the actual fault — an unreachable database — was reported nowhere.

The split
---------
An *infrastructure* failure means the request never got a verdict: DNS did not
resolve, the connection was refused, the read timed out. Nothing is known about
the credentials, so the honest answer is 503 Service Unavailable — "try again,
it isn't you".

Anything else means Supabase answered and said no. That is a real 401.

We identify infrastructure failures by type rather than by matching text,
because error messages change between library versions and matching on strings
would quietly stop working.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

# httpx.TransportError covers ConnectError, ConnectTimeout, ReadTimeout,
# NetworkError and friends — everything that means "the request never landed".
# OSError covers lower-level socket failures such as socket.gaierror, which is
# what a DNS lookup raises when a hostname does not resolve.
INFRASTRUCTURE_ERRORS: tuple[type[BaseException], ...] = (httpx.TransportError, OSError)


# How far to follow the chain. Real chains are 3-4 deep; the limit just stops
# a pathological or self-referencing chain from looping forever.
_MAX_CHAIN_DEPTH = 10


def is_infrastructure_error(exc: BaseException) -> bool:
    """True if this exception means we never reached Supabase at all.

    Follows the exception chain rather than only checking the type in hand.
    That is not defensive programming — it is required. The supabase library
    catches httpx's error and re-raises its own `AuthRetryableError`, which is a
    plain Exception with no relationship to httpx. Checking only the outermost
    type sees an ordinary error and reports a total outage as a bad password.

    The chain observed from the real library:

        AuthRetryableError  <- what we are handed
          __cause__ -> httpx.ConnectError
            __cause__ -> socket.gaierror

    `__cause__` is set by `raise X from Y`; `__context__` is set automatically
    when one exception is raised while handling another. Libraries use both, so
    we follow whichever is present.
    """
    seen: set[int] = set()
    current: BaseException | None = exc

    for _ in range(_MAX_CHAIN_DEPTH):
        if current is None or id(current) in seen:
            return False
        if isinstance(current, INFRASTRUCTURE_ERRORS):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__

    return False


def log_upstream_failure(operation: str, exc: BaseException) -> None:
    """Record the real error on the server, where it is useful and private.

    The caller gets a generic message; the full detail belongs in the logs, not
    in an HTTP response body.
    """
    logger.warning("%s failed: %s: %s", operation, type(exc).__name__, exc)
