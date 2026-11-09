"""Guest accounts are free to create, so creating them is rate limited per IP.

Not a guarantee against a determined abuser (they can change network); it stops
one person or a simple script creating guests in a loop.
"""

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.core.rate_limit import RateLimiter, client_ip


def _limiter(limit=5, window=3600.0):
    now = [1000.0]
    limiter = RateLimiter(limit, window, clock=lambda: now[0])
    return limiter, now


def test_the_limit_allows_up_to_n_then_says_how_long_to_wait():
    limiter, now = _limiter(limit=5)

    assert [limiter.hit("1.2.3.4") for _ in range(5)] == [None] * 5
    now[0] += 600  # ten minutes later, still inside the hour
    assert limiter.hit("1.2.3.4") == pytest.approx(3000)  # the oldest frees up in 50 min


def test_each_ip_has_its_own_limit():
    limiter, _ = _limiter(limit=1)

    assert limiter.hit("1.1.1.1") is None
    assert limiter.hit("2.2.2.2") is None
    assert limiter.hit("1.1.1.1") is not None


def test_the_limit_frees_up_once_the_window_has_passed():
    limiter, now = _limiter(limit=1, window=3600)

    assert limiter.hit("1.1.1.1") is None
    now[0] += 3600
    assert limiter.hit("1.1.1.1") is None


def test_a_refused_attempt_does_not_extend_the_wait():
    limiter, now = _limiter(limit=1, window=3600)
    limiter.hit("1.1.1.1")

    for _ in range(10):
        now[0] += 60
        limiter.hit("1.1.1.1")

    now[0] = 1000.0 + 3600
    assert limiter.hit("1.1.1.1") is None


def _request(headers=None, host="10.0.0.1"):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "client": (host, 1234)})


def test_the_ip_is_the_last_forwarded_for_entry():
    """The proxy appends the real address; anything before it came from the
    visitor and could be made up."""
    request = _request({"X-Forwarded-For": "6.6.6.6, 203.0.113.9"})

    assert client_ip(request) == "203.0.113.9"


def test_without_a_proxy_header_the_connection_address_is_used():
    assert client_ip(_request(host="192.168.1.20")) == "192.168.1.20"


# --- the guest endpoint itself -------------------------------------------------


@pytest.fixture
def guests_succeed(monkeypatch):
    def sign_in_anonymously():
        return SimpleNamespace(
            user=SimpleNamespace(id="g1", email="", is_anonymous=True),
            session=SimpleNamespace(access_token="a", refresh_token="r", expires_in=3600),
        )

    stub = SimpleNamespace(auth=SimpleNamespace(sign_in_anonymously=sign_in_anonymously))
    monkeypatch.setattr("app.api.v1.auth.get_anon_client", lambda: stub)


def _guest(client, ip):
    return client.post("/v1/auth/anonymous", headers={"X-Forwarded-For": ip})


def test_the_sixth_guest_from_one_ip_in_an_hour_is_429(client, guests_succeed):
    assert [_guest(client, "203.0.113.9").status_code for _ in range(5)] == [201] * 5

    response = _guest(client, "203.0.113.9")

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert _guest(client, "198.51.100.7").status_code == 201  # another network is unaffected


def test_a_made_up_forwarded_for_entry_does_not_dodge_the_limit(client, guests_succeed):
    for i in range(5):
        client.post("/v1/auth/anonymous", headers={"X-Forwarded-For": f"9.9.9.{i}, 203.0.113.9"})

    response = client.post("/v1/auth/anonymous", headers={"X-Forwarded-For": "9.9.9.99, 203.0.113.9"})

    assert response.status_code == 429


def test_a_refused_guest_never_reaches_supabase(client, monkeypatch, guests_succeed):
    for _ in range(5):
        _guest(client, "203.0.113.9")

    def boom():
        raise AssertionError("Supabase was called despite the limit")

    monkeypatch.setattr("app.api.v1.auth.get_anon_client", boom)

    assert _guest(client, "203.0.113.9").status_code == 429


def test_login_is_not_limited_by_the_guest_limit(client, failing_supabase):
    failing_supabase(Exception("Invalid login credentials"))

    codes = {
        client.post("/v1/auth/login", json={"email": "a@example.com", "password": "x"}).status_code
        for _ in range(7)
    }

    assert codes == {401}
