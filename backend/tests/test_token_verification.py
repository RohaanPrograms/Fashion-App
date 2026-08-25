"""Access tokens should be verified here, not by asking Supabase every time.

Why this change exists
----------------------
Every authenticated request used to call Supabase to ask "is this token any
good?" — a full network round trip before the endpoint could even start. In
Phase 1 every swipe hits POST /v1/interactions, so that round trip would double
the latency of the busiest endpoint in the app and spend Supabase quota per
swipe.

A Supabase access token is a JWT ("JSON Web Token") — a blob with three parts:
some claims (who you are, when it expires) and a signature proving Supabase
issued it. The signature is made with the project's JWT secret. Anyone holding
that secret can check the signature themselves, offline, in microseconds. That
is the whole idea: same guarantee, no network.

What we must NOT lose in the process: a forged, expired, or tampered token has
to be rejected just as firmly as before.
"""

import time

import jwt as pyjwt
import pytest

# At least 32 bytes: PyJWT warns below that for HS256, and a real Supabase JWT
# secret is longer still. Neither of these is a real secret.
SECRET = "test-jwt-secret-for-unit-tests-0123456789"
OTHER_SECRET = "a-completely-different-test-secret-9876543210"
USER_ID = "11111111-2222-3333-4444-555555555555"


def make_token(secret=SECRET, *, expires_in=3600, audience="authenticated", **overrides):
    """Mint a token shaped like a real Supabase access token."""
    now = int(time.time())
    claims = {
        "sub": USER_ID,
        "email": "person@example.com",
        "aud": audience,
        "role": "authenticated",
        "iat": now,
        "exp": now + expires_in,
    }
    claims.update(overrides)
    return pyjwt.encode(claims, secret, algorithm="HS256")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_valid_token_is_accepted_without_calling_supabase(
    client, auth_settings, no_network
):
    """The point of the change: a good token needs no network round trip."""
    auth_settings(jwt_secret=SECRET)

    response = client.get("/v1/auth/me", headers=auth(make_token()))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == USER_ID
    assert body["email"] == "person@example.com"


def test_expired_token_is_rejected(client, auth_settings, no_network):
    auth_settings(jwt_secret=SECRET)

    response = client.get("/v1/auth/me", headers=auth(make_token(expires_in=-60)))

    assert response.status_code == 401


def test_token_signed_with_the_wrong_secret_is_rejected(client, auth_settings, no_network):
    """A token someone else minted must not be accepted."""
    auth_settings(jwt_secret=SECRET)

    response = client.get("/v1/auth/me", headers=auth(make_token(secret=OTHER_SECRET)))

    assert response.status_code == 401


def test_unsigned_token_is_rejected(client, auth_settings, no_network):
    """The classic JWT attack: strip the signature and set algorithm to "none".

    If the verifier accepts it, anyone can mint a token for any user by editing
    a text string. It must be refused.
    """
    auth_settings(jwt_secret=SECRET)
    forged = pyjwt.encode({"sub": USER_ID, "aud": "authenticated"}, key="", algorithm="none")

    response = client.get("/v1/auth/me", headers=auth(forged))

    assert response.status_code == 401


def test_token_with_tampered_claims_is_rejected(client, auth_settings, no_network):
    """Changing the payload invalidates the signature."""
    auth_settings(jwt_secret=SECRET)
    header, payload, signature = make_token().split(".")
    other_payload = make_token(sub="99999999-9999-9999-9999-999999999999").split(".")[1]

    response = client.get("/v1/auth/me", headers=auth(f"{header}.{other_payload}.{signature}"))

    assert response.status_code == 401


@pytest.mark.parametrize("bad", ["", "not-a-jwt", "a.b.c", "Bearer-ish-nonsense"])
def test_malformed_tokens_are_rejected(client, auth_settings, no_network, bad):
    auth_settings(jwt_secret=SECRET)

    response = client.get("/v1/auth/me", headers=auth(bad))

    assert response.status_code in (401, 403)


def test_token_for_the_wrong_audience_is_rejected(client, auth_settings, no_network):
    """Supabase issues user tokens with aud="authenticated".

    A token minted for some other audience — even correctly signed — is not a
    user session token and must not be treated as one.
    """
    auth_settings(jwt_secret=SECRET)

    response = client.get("/v1/auth/me", headers=auth(make_token(audience="some-other-app")))

    assert response.status_code == 401


def test_token_without_an_expiry_is_rejected(client, auth_settings, no_network):
    """A token with no `exp` claim would be valid forever. Refuse it.

    Supabase always sets one; a token without it did not come from a normal
    session and must not be honoured indefinitely.
    """
    auth_settings(jwt_secret=SECRET)
    now = int(time.time())
    no_expiry = pyjwt.encode(
        {"sub": USER_ID, "aud": "authenticated", "iat": now}, SECRET, algorithm="HS256"
    )

    response = client.get("/v1/auth/me", headers=auth(no_expiry))

    assert response.status_code == 401


def test_token_without_a_subject_is_rejected(client, auth_settings, no_network):
    """`sub` is the user id. Without it we do not know who is calling.

    This also protects the endpoint from crashing: the code reads claims["sub"],
    so an accepted token missing it would raise a 500 instead of a clean 401.
    """
    auth_settings(jwt_secret=SECRET)
    now = int(time.time())
    no_subject = pyjwt.encode(
        {"aud": "authenticated", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm="HS256",
    )

    response = client.get("/v1/auth/me", headers=auth(no_subject))

    assert response.status_code == 401


def test_falls_back_to_supabase_when_no_secret_is_configured(
    client, auth_settings, failing_supabase
):
    """With no secret set, behaviour is unchanged — the network path still runs.

    This keeps a deployment that has not set SUPABASE_JWT_SECRET working exactly
    as it does today, rather than locking every user out.
    """
    auth_settings(jwt_secret="")
    failing_supabase(Exception("Invalid token"))

    response = client.get("/v1/auth/me", headers=auth(make_token()))

    assert response.status_code == 401  # network path ran and rejected it


def test_falls_back_to_supabase_when_the_secret_does_not_match_the_project(
    client, auth_settings, failing_supabase
):
    """A wrong secret must not lock every user out of the app.

    This is not hypothetical: during this work the secret was set to a UUID —
    a JWT signing-key *id* copied instead of the secret itself. With naive
    local verification, every correctly-signed token would fail its signature
    check and every user would get 401 with no clue why.

    We can detect it for free: the project's own anon key is a JWT signed with
    the same secret. If our secret cannot verify the anon key, it is the wrong
    secret, so we log loudly and keep using the network path.
    """
    # Secret is set, but the anon key was signed with a DIFFERENT one.
    auth_settings(jwt_secret=OTHER_SECRET, anon_signed_with=SECRET)
    failing_supabase(Exception("Invalid token"))

    # A token correctly signed for the real project would fail a naive local
    # check. Falling back means Supabase gets to decide, as it does today.
    response = client.get("/v1/auth/me", headers=auth(make_token(secret=SECRET)))

    assert response.status_code == 401  # reached the network path, not a crash


def test_a_matching_secret_enables_local_verification(auth_settings):
    """The detection itself: matching secret -> local verification is on."""
    from app.core.security import uses_local_verification

    auth_settings(jwt_secret=SECRET)
    assert uses_local_verification() is True


def test_a_mismatched_secret_disables_local_verification(auth_settings):
    from app.core.security import uses_local_verification

    auth_settings(jwt_secret=OTHER_SECRET, anon_signed_with=SECRET)
    assert uses_local_verification() is False
