"""Guest accounts are free to create, so creating them is rate limited per IP.

Not a guarantee against a determined abuser (they can change network); it stops
one person or a simple script creating guests in a loop.

Which IP? Behind Railway's proxy every connection comes from the proxy, so the
visitor's address has to come from a header the proxy sets (X-Real-IP). But a
header is only trustworthy if a proxy really sets it: without one, a visitor
can write anything into it. So a header is used only when CLIENT_IP_HEADER
names it, and never otherwise.
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


def test_with_no_proxy_configured_headers_are_ignored():
    """Without a proxy, these headers came from the visitor and prove nothing."""
    request = _request({"X-Real-IP": "6.6.6.6", "X-Forwarded-For": "6.6.6.6"}, host="192.168.1.20")

    assert client_ip(request, trusted_header="") == "192.168.1.20"


def test_the_configured_proxy_header_is_used():
    request = _request({"X-Real-IP": "203.0.113.9"})

    assert client_ip(request, trusted_header="X-Real-IP") == "203.0.113.9"


def test_x_forwarded_for_is_never_used_unless_it_is_the_configured_header():
    request = _request({"X-Forwarded-For": "6.6.6.6", "X-Real-IP": "203.0.113.9"})

    assert client_ip(request, trusted_header="X-Real-IP") == "203.0.113.9"


def test_a_configured_header_that_is_missing_falls_back_to_the_connection():
    assert client_ip(_request(host="192.168.1.20"), trusted_header="X-Real-IP") == "192.168.1.20"


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


@pytest.fixture
def behind_railway(monkeypatch):
    """Configured as in production: Railway's proxy puts the visitor's IP in X-Real-IP."""
    from app.core.config import Settings

    settings = Settings(SUPABASE_URL="https://example.supabase.co", CLIENT_IP_HEADER="X-Real-IP")
    monkeypatch.setattr("app.api.v1.auth.get_settings", lambda: settings)


def _guest(client, ip, **extra_headers):
    return client.post("/v1/auth/anonymous", headers={"X-Real-IP": ip, **extra_headers})


def test_the_sixth_guest_from_one_ip_in_an_hour_is_429(client, guests_succeed, behind_railway):
    assert [_guest(client, "203.0.113.9").status_code for _ in range(5)] == [201] * 5

    response = _guest(client, "203.0.113.9")

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert _guest(client, "198.51.100.7").status_code == 201  # another network is unaffected


def test_a_made_up_forwarded_for_does_not_dodge_the_limit(client, guests_succeed, behind_railway):
    for i in range(5):
        _guest(client, "203.0.113.9", **{"X-Forwarded-For": f"9.9.9.{i}"})

    assert _guest(client, "203.0.113.9", **{"X-Forwarded-For": "9.9.9.99"}).status_code == 429


def test_without_a_proxy_a_made_up_header_does_not_dodge_the_limit(client, guests_succeed):
    """Default settings: the header is ignored, so every request is the same caller."""
    codes = [_guest(client, f"9.9.9.{i}").status_code for i in range(6)]

    assert codes == [201] * 5 + [429]


def test_a_refused_guest_never_reaches_supabase(client, monkeypatch, guests_succeed):
    for _ in range(5):
        client.post("/v1/auth/anonymous")

    def boom():
        raise AssertionError("Supabase was called despite the limit")

    monkeypatch.setattr("app.api.v1.auth.get_anon_client", boom)

    assert client.post("/v1/auth/anonymous").status_code == 429


def test_login_is_not_limited_by_the_guest_limit(client, failing_supabase):
    failing_supabase(Exception("Invalid login credentials"))

    codes = {
        client.post("/v1/auth/login", json={"email": "a@example.com", "password": "x"}).status_code
        for _ in range(7)
    }

    assert codes == {401}
