"""Saving a guest's account with a verified email, keeping the same id.

start    -> Supabase emails a one-time code
verify   -> the code turns the guest into a normal account (fresh session)
password -> the now-verified account gets a password

Supabase Auth itself is replaced by a fake; app.core.gotrue's own tests
cover the real HTTP calls.
"""

from types import SimpleNamespace

import httpx
import pytest

from app.api.deps import get_bearer_token, get_current_user
from app.core.gotrue import GoTrueError
from app.main import app
from app.schemas.auth import UserOut

GUEST_ID = "99999999-1111-4111-8111-999999999999"
EMAIL = "new@example.com"


class FakeGoTrue:
    def __init__(self):
        self.error: Exception | None = None
        self.verified_user_id = GUEST_ID
        self.calls: list[tuple] = []

    def _maybe_fail(self):
        if self.error is not None:
            raise self.error

    def request_email_change(self, token, email):
        self.calls.append(("email", token, email))
        self._maybe_fail()

    def verify_email_change(self, email, code):
        self.calls.append(("verify", email, code))
        self._maybe_fail()
        return {
            "access_token": "fresh",
            "refresh_token": "fresh-refresh",
            "expires_in": 3600,
            "token_type": "bearer",
            "user": {"id": self.verified_user_id, "email": email, "is_anonymous": False},
        }

    def set_password(self, token, password):
        self.calls.append(("password", token, password))
        self._maybe_fail()


class FakeAdmin:
    def __init__(self):
        self.is_anonymous = True

    def get_user_by_id(self, uid):
        return SimpleNamespace(user=SimpleNamespace(id=uid, email="", is_anonymous=self.is_anonymous))


@pytest.fixture
def auth(client, monkeypatch):
    """Signed in as a guest; Supabase Auth and the admin lookup are fakes."""
    fake, admin = FakeGoTrue(), FakeAdmin()
    for name in ("request_email_change", "verify_email_change", "set_password"):
        monkeypatch.setattr(f"app.api.v1.auth.gotrue.{name}", getattr(fake, name))
    monkeypatch.setattr(
        "app.api.v1.auth.get_service_client",
        lambda: SimpleNamespace(auth=SimpleNamespace(admin=admin)),
    )
    current = {"user": UserOut(id=GUEST_ID, is_anonymous=True)}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.dependency_overrides[get_bearer_token] = lambda: "caller-token"

    def post(path, body):
        return client.post(path, json=body, headers={"Authorization": "Bearer caller-token"})

    yield SimpleNamespace(fake=fake, admin=admin, current=current, post=post)
    app.dependency_overrides.clear()


# --- start ------------------------------------------------------------------


def test_start_sends_the_code_as_the_caller(auth):
    response = auth.post("/v1/auth/upgrade/start", {"email": EMAIL})

    assert response.status_code == 202
    assert response.json() == {"email": EMAIL}
    assert auth.fake.calls == [("email", "caller-token", EMAIL)]


def test_start_refuses_an_account_that_already_has_an_email(auth):
    # The token may still say "guest" for up to an hour; the database decides.
    auth.admin.is_anonymous = False

    response = auth.post("/v1/auth/upgrade/start", {"email": EMAIL})

    assert response.status_code == 409
    assert auth.fake.calls == []


def test_start_with_an_email_already_registered_is_409(auth):
    auth.fake.error = GoTrueError(
        422, "email_exists", "A user with this email address has already been registered"
    )

    response = auth.post("/v1/auth/upgrade/start", {"email": EMAIL})

    assert response.status_code == 409
    assert "log in" in response.json()["detail"].lower()


def test_asking_again_too_soon_is_429(auth):
    auth.fake.error = GoTrueError(
        429,
        "over_email_send_rate_limit",
        "For security purposes, you can only request this after 52 seconds.",
    )

    response = auth.post("/v1/auth/upgrade/start", {"email": EMAIL})

    assert response.status_code == 429
    assert "52 seconds" not in response.json()["detail"]  # our words, not Supabase's


def test_an_email_that_cannot_be_sent_is_503_without_leaking(auth):
    auth.fake.error = GoTrueError(
        500, "unexpected_failure", "Error sending confirmation email: smtp auth failed"
    )

    response = auth.post("/v1/auth/upgrade/start", {"email": EMAIL})

    assert response.status_code == 503
    assert "smtp" not in response.json()["detail"].lower()


def test_start_during_an_outage_is_503(auth):
    auth.fake.error = httpx.ConnectError("refused")

    assert auth.post("/v1/auth/upgrade/start", {"email": EMAIL}).status_code == 503


def test_start_with_a_bad_email_is_422(auth):
    assert auth.post("/v1/auth/upgrade/start", {"email": "nope"}).status_code == 422
    assert auth.fake.calls == []


# --- verify -----------------------------------------------------------------


def test_the_right_code_keeps_the_id_and_returns_a_fresh_session(auth):
    response = auth.post("/v1/auth/upgrade/verify", {"email": EMAIL, "code": "123456"})

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {"id": GUEST_ID, "email": EMAIL, "is_anonymous": False}
    assert body["session"]["access_token"] == "fresh"
    assert body["session"]["refresh_token"] == "fresh-refresh"
    assert auth.fake.calls == [("verify", EMAIL, "123456")]


def test_a_wrong_or_expired_code_is_400(auth):
    auth.fake.error = GoTrueError(403, "otp_expired", "Token has expired or is invalid")

    response = auth.post("/v1/auth/upgrade/verify", {"email": EMAIL, "code": "000000"})

    assert response.status_code == 400
    assert "new code" in response.json()["detail"]


def test_a_code_for_someone_elses_account_is_refused(auth):
    auth.fake.verified_user_id = "another-user"

    response = auth.post("/v1/auth/upgrade/verify", {"email": EMAIL, "code": "123456"})

    assert response.status_code == 403
    assert "session" not in response.json()


@pytest.mark.parametrize("code", ["12ab56", "123", ""])
def test_a_malformed_code_is_422(auth, code):
    assert auth.post("/v1/auth/upgrade/verify", {"email": EMAIL, "code": code}).status_code == 422
    assert auth.fake.calls == []


def test_verify_during_an_outage_is_503(auth):
    auth.fake.error = httpx.ReadTimeout("timed out")

    response = auth.post("/v1/auth/upgrade/verify", {"email": EMAIL, "code": "123456"})

    assert response.status_code == 503


# --- password ---------------------------------------------------------------


def test_a_verified_account_sets_its_password(auth):
    auth.current["user"] = UserOut(id=GUEST_ID, email=EMAIL, is_anonymous=False)

    response = auth.post("/v1/auth/password", {"password": "correct-horse-battery"})

    assert response.status_code == 204
    assert auth.fake.calls == [("password", "caller-token", "correct-horse-battery")]


def test_a_guest_cannot_set_a_password_before_verifying(auth):
    response = auth.post("/v1/auth/password", {"password": "correct-horse-battery"})

    assert response.status_code == 409
    assert auth.fake.calls == []


def test_a_refused_password_is_400_without_leaking(auth):
    auth.current["user"] = UserOut(id=GUEST_ID, email=EMAIL, is_anonymous=False)
    auth.fake.error = GoTrueError(
        422, "weak_password", "Password is known to be weak and easy to guess (pwned)"
    )

    response = auth.post("/v1/auth/password", {"password": "password123"})

    assert response.status_code == 400
    assert "pwned" not in response.json()["detail"]


def test_a_short_password_is_422(auth):
    auth.current["user"] = UserOut(id=GUEST_ID, email=EMAIL, is_anonymous=False)

    assert auth.post("/v1/auth/password", {"password": "short"}).status_code == 422
