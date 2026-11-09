"""Guest accounts: a real Supabase user with no email, so visitors can swipe
immediately. Supabase gives these accounts an EMPTY-STRING email, which is not
a valid address — before the fix, every request from a guest crashed with 500.
"""

import time
from types import SimpleNamespace

import httpx
import jwt as pyjwt

SECRET = "test-jwt-secret-for-unit-tests-0123456789"
GUEST_ID = "99999999-1111-4111-8111-999999999999"


def _guest_token():
    now = int(time.time())
    claims = {
        "sub": GUEST_ID, "email": "", "is_anonymous": True, "aud": "authenticated",
        "role": "authenticated", "iat": now, "exp": now + 3600,
    }
    return pyjwt.encode(claims, SECRET, algorithm="HS256")


def _guest_result():
    return SimpleNamespace(
        user=SimpleNamespace(id=GUEST_ID, email="", is_anonymous=True),
        session=SimpleNamespace(access_token="access", refresh_token="refresh", expires_in=3600),
    )


def test_a_guest_session_is_created(client, monkeypatch):
    stub = SimpleNamespace(auth=SimpleNamespace(sign_in_anonymously=_guest_result))
    monkeypatch.setattr("app.api.v1.auth.get_anon_client", lambda: stub)

    response = client.post("/v1/auth/anonymous")

    assert response.status_code == 201
    body = response.json()
    assert body["user"] == {"id": GUEST_ID, "email": None, "is_anonymous": True}
    assert body["session"]["access_token"] == "access"


def test_a_guest_token_is_accepted_by_local_verification(client, auth_settings, no_network):
    auth_settings(jwt_secret=SECRET)

    response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {_guest_token()}"})

    assert response.status_code == 200
    assert response.json() == {"id": GUEST_ID, "email": None, "is_anonymous": True}


def test_a_guest_token_is_accepted_by_network_verification(client, monkeypatch):
    stub = SimpleNamespace(
        auth=SimpleNamespace(get_user=lambda token: SimpleNamespace(user=_guest_result().user))
    )
    monkeypatch.setattr("app.api.deps.get_anon_client", lambda: stub)

    response = client.get("/v1/auth/me", headers={"Authorization": "Bearer anything"})

    assert response.status_code == 200
    assert response.json()["email"] is None


def test_regular_users_are_not_marked_as_guests(client, auth_settings, no_network):
    auth_settings(jwt_secret=SECRET)
    now = int(time.time())
    token = pyjwt.encode(
        {"sub": "u1", "email": "a@example.com", "aud": "authenticated", "iat": now, "exp": now + 60},
        SECRET, algorithm="HS256",
    )

    body = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()

    assert body == {"id": "u1", "email": "a@example.com", "is_anonymous": False}


def test_guest_sign_in_switched_off_in_supabase_is_503_without_leaking(client, failing_supabase):
    failing_supabase(Exception("Anonymous sign-ins are disabled"))

    response = client.post("/v1/auth/anonymous")

    assert response.status_code == 503
    assert "disabled" not in response.json()["detail"]


def test_guest_sign_in_during_an_outage_is_503(client, failing_supabase):
    failing_supabase(httpx.ConnectError("refused"))

    response = client.post("/v1/auth/anonymous")

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
