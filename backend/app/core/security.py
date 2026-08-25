"""Verifying Supabase access tokens locally instead of over the network.

The problem this solves
-----------------------
Asking Supabase to validate every incoming token costs a full network round
trip per request. In Phase 1 every swipe hits POST /v1/interactions, so that
would double the latency of the busiest endpoint in the app and spend Supabase
quota on each one.

How a token can be checked offline
----------------------------------
A Supabase access token is a JWT ("JSON Web Token"): a base64 blob holding
claims — who the user is (`sub`), when it expires (`exp`), who it was issued for
(`aud`) — plus a signature. Supabase produces that signature with the project's
JWT secret. Anyone holding the same secret can recompute it and confirm the
token is genuine and unaltered, in microseconds, with no network involved.

The safety rail
---------------
A wrong secret would reject every genuine token and lock every user out of the
app, with a 401 that looks exactly like a bad password. That is not theoretical:
while this was being built, the secret had been set to a UUID — a JWT signing
key *id*, copied from the dashboard instead of the secret itself.

We can catch that for free. The project's own anon key is a JWT signed with the
same secret, so if our secret cannot verify the anon key, our secret is wrong.
When that happens we log loudly and keep using the network path, which still
works. A misconfiguration then costs latency instead of a total outage.
"""

import logging
from functools import lru_cache

import jwt
from jwt import PyJWTError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Supabase issues user session tokens with this audience. A correctly-signed
# token minted for anything else is not a user session and must not be accepted.
AUDIENCE = "authenticated"

# Supabase's shared-secret tokens are HMAC-SHA256. Pinning the algorithm list is
# a security requirement, not a detail: without it, a caller could hand us a
# token with its algorithm set to "none" and no signature at all, and a naive
# verifier would accept whatever claims it liked.
ALGORITHMS = ["HS256"]


@lru_cache
def uses_local_verification() -> bool:
    """Can we trust this JWT secret enough to verify tokens ourselves?

    Cached: the answer depends only on configuration, and this runs on every
    authenticated request.
    """
    settings = get_settings()

    if not settings.SUPABASE_JWT_SECRET:
        # Nothing configured — behave exactly as before.
        return False

    anon_key = settings.SUPABASE_ANON_KEY
    if not anon_key:
        logger.warning(
            "SUPABASE_JWT_SECRET is set but SUPABASE_ANON_KEY is not, so the "
            "secret cannot be checked. Using network token verification."
        )
        return False

    try:
        # Only the signature matters here. The anon key's audience is irrelevant
        # and it may legitimately be long-lived or expired.
        jwt.decode(
            anon_key,
            settings.SUPABASE_JWT_SECRET,
            algorithms=ALGORITHMS,
            options={"verify_aud": False, "verify_exp": False},
        )
    except jwt.InvalidSignatureError:
        logger.error(
            "SUPABASE_JWT_SECRET does not match this Supabase project: it cannot "
            "verify the project's own anon key. Falling back to network token "
            "verification so users are not locked out. Fix: Supabase dashboard "
            "-> Project Settings -> API -> JWT Settings -> JWT Secret. Note this "
            "is the long secret string, NOT the signing key's UUID id."
        )
        return False
    except PyJWTError as exc:
        # e.g. the project uses the newer publishable key format, which is not a
        # JWT — then we cannot self-check, so we do not risk local verification.
        logger.warning(
            "Could not check SUPABASE_JWT_SECRET against the anon key (%s: %s). "
            "Using network token verification.",
            type(exc).__name__,
            exc,
        )
        return False

    logger.info("JWT secret verified against the project — using local token verification.")
    return True


def decode_access_token(token: str) -> dict:
    """Verify a Supabase access token and return its claims.

    Raises PyJWTError (the base class for every JWT failure: bad signature,
    expired, malformed, wrong audience) if the token is not acceptable.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.SUPABASE_JWT_SECRET,
        algorithms=ALGORITHMS,
        audience=AUDIENCE,
        # A token with no expiry would never expire, and one with no subject
        # tells us nothing about who is calling. Neither is a usable session.
        options={"require": ["exp", "sub"]},
    )
