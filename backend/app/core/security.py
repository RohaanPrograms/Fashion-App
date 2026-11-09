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

Newer signing keys (ES256)
--------------------------
That shared-secret scheme is Supabase's legacy one. Projects on its newer
signing keys sign access tokens with ES256: a private key Supabase never
shares, checked with a public key it publishes at
<project>/auth/v1/.well-known/jwks.json (a "JWKS", JSON Web Key Set). No secret
is needed — the published key can verify a token but never create one.

The trap this closes: on such a project the anon key is still signed with the
legacy secret, so the self-check above passes, while every user token is ES256
and the HS256-only check refused them all. Each token's own header now says
which scheme signed it, and ES256 tokens are checked against the published keys.
"""

import logging
from functools import lru_cache

import jwt
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWTError

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

# Public-key schemes Supabase's signing keys use. Kept apart from ALGORITHMS on
# purpose: a token claiming one of these is only ever checked against a
# published public key, and an HS256 token only ever against the secret, so a
# token cannot pick the scheme that suits a forger.
ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")

# How long the downloaded key list is trusted before it is fetched again. A
# token signed by a key not in the list also triggers one refetch, so a key
# rotation is picked up straight away.
JWKS_CACHE_SECONDS = 600


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


def jwks_url(supabase_url: str) -> str:
    """Where a Supabase project publishes its public signing keys."""
    return f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


@lru_cache
def jwks_client() -> PyJWKClient | None:
    """One shared key-list client, so the list is downloaded once and cached."""
    settings = get_settings()
    if not settings.SUPABASE_URL:
        return None
    return PyJWKClient(
        jwks_url(settings.SUPABASE_URL), cache_jwk_set=True, lifespan=JWKS_CACHE_SECONDS, timeout=5
    )


def verify_locally(token: str) -> dict | None:
    """Check a token here if possible; return its claims.

    Returns None when it cannot be checked locally — then the caller asks
    Supabase, exactly as before local verification existed. Raises PyJWTError
    when the token is checked and is not acceptable (forged, expired, wrong
    audience, signed by a key the project never published).
    """
    try:
        algorithm = jwt.get_unverified_header(token).get("alg")
    except PyJWTError:
        algorithm = None  # not a readable JWT; handled below like any other

    if algorithm in ASYMMETRIC_ALGORITHMS:
        client = jwks_client()
        if client is None:
            return None
        try:
            signing_key = client.get_signing_key_from_jwt(token)
        except PyJWKClientConnectionError as exc:
            # Could not download the key list. Not the caller's fault: ask
            # Supabase instead of locking every user out.
            logger.warning("Could not fetch the public signing keys (%s); asking Supabase.", exc)
            return None
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience=AUDIENCE,
            options={"require": ["exp", "sub"]},
        )

    if uses_local_verification():
        # Legacy shared-secret project: unchanged behaviour. Anything that is
        # not a valid HS256 token (including alg "none") is refused here.
        return decode_access_token(token)
    return None


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
