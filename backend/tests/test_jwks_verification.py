"""Verifying ES256 access tokens with the project's published public keys.

Why this exists
---------------
Supabase's newer signing keys sign access tokens with ES256: a private key
Supabase never shares, checked with a public key it publishes at
<project>/auth/v1/.well-known/jwks.json. The original local check only knew
HS256 (the shared legacy secret), so once the project moved to the new keys,
every real user's token was rejected with 401 — while the self-check still
passed, because the anon key is still signed the old way.

These tests sign tokens the new way, with a key pair made fresh per test, and
stand in a fake for the published key list so nothing touches the network.
"""

import base64
import json
import time
from types import SimpleNamespace

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.security import jwks_url

KID = "project-signing-key-1"
USER_ID = "11111111-2222-3333-4444-555555555555"


def _private_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def project_keys(monkeypatch):
    """The project's published public keys, without the network."""
    private = _private_key()
    published = {KID: private.public_key()}

    class FakeKeyList:
        def get_signing_key_from_jwt(self, token):
            kid = pyjwt.get_unverified_header(token).get("kid")
            if kid not in published:
                raise pyjwt.PyJWKClientError(f"Unable to find a signing key that matches: {kid}")
            return SimpleNamespace(key=published[kid])

    monkeypatch.setattr("app.core.security.jwks_client", lambda: FakeKeyList())
    return SimpleNamespace(private=private)


def es256(private, *, kid=KID, expires_in=3600, audience="authenticated", **overrides):
    now = int(time.time())
    claims = {
        "sub": USER_ID, "email": "person@example.com", "aud": audience,
        "role": "authenticated", "iat": now, "exp": now + expires_in,
    }
    claims.update(overrides)
    return pyjwt.encode(claims, private, algorithm="ES256", headers={"kid": kid})


def _me(client, token):
    return client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_a_token_signed_by_the_projects_key_is_accepted_without_calling_supabase(
    client, project_keys, no_network
):
    response = _me(client, es256(project_keys.private))

    assert response.status_code == 200
    assert response.json() == {"id": USER_ID, "email": "person@example.com", "is_anonymous": False}


def test_a_guest_token_signed_with_es256_is_accepted(client, project_keys, no_network):
    """The exact token shape a real guest got back from Supabase, which was refused."""
    token = es256(project_keys.private, email="", is_anonymous=True)

    response = _me(client, token)

    assert response.status_code == 200
    assert response.json() == {"id": USER_ID, "email": None, "is_anonymous": True}


def test_a_token_signed_by_someone_elses_key_is_rejected(client, project_keys, no_network):
    forged = es256(_private_key())  # same key id, wrong private key

    assert _me(client, forged).status_code == 401


def test_a_key_id_the_project_never_published_is_rejected(client, project_keys, no_network):
    assert _me(client, es256(project_keys.private, kid="not-ours")).status_code == 401


def test_an_expired_token_is_rejected(client, project_keys, no_network):
    assert _me(client, es256(project_keys.private, expires_in=-60)).status_code == 401


def test_a_token_for_another_audience_is_rejected(client, project_keys, no_network):
    assert _me(client, es256(project_keys.private, audience="something-else")).status_code == 401


def test_a_tampered_token_is_rejected(client, project_keys, no_network):
    header, _, signature = es256(project_keys.private).split(".")
    now = int(time.time())
    claims = {"sub": "someone-else", "aud": "authenticated", "iat": now, "exp": now + 3600}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()

    assert _me(client, f"{header}.{payload}.{signature}").status_code == 401


def test_if_the_public_keys_cannot_be_fetched_supabase_is_asked_instead(client, monkeypatch):
    """Failing to download the key list must not lock everyone out."""

    class Unreachable:
        def get_signing_key_from_jwt(self, token):
            raise pyjwt.PyJWKClientConnectionError("connection refused")

    monkeypatch.setattr("app.core.security.jwks_client", lambda: Unreachable())
    user = SimpleNamespace(id=USER_ID, email="person@example.com", is_anonymous=False)
    stub = SimpleNamespace(auth=SimpleNamespace(get_user=lambda token: SimpleNamespace(user=user)))
    monkeypatch.setattr("app.api.deps.get_anon_client", lambda: stub)

    response = _me(client, es256(_private_key()))

    assert response.status_code == 200


def test_the_key_list_address_is_the_projects_published_one():
    assert jwks_url("https://abc.supabase.co") == "https://abc.supabase.co/auth/v1/.well-known/jwks.json"
    assert jwks_url("https://abc.supabase.co/") == "https://abc.supabase.co/auth/v1/.well-known/jwks.json"
