"""The auth endpoints must tell the truth about *why* a request failed.

The bug these tests exist to prevent: when Supabase was unreachable, every auth
endpoint reported "Invalid email or password". A user with perfectly good
credentials was told their password was wrong, and the real fault — an offline
database — was invisible. It even fooled a verification script into reporting
that Supabase was reachable.

The distinction that matters:
  - The service could not be reached      -> 503 Service Unavailable ("not you")
  - The service rejected the credentials  -> 401 Unauthorized        ("it's you")
"""

import httpx
import pytest


class _LibraryWrappedError(Exception):
    """Stands in for supabase's AuthRetryableError.

    Named to make the point: it is an ordinary Exception, unrelated to httpx by
    type. We define our own rather than importing gotrue's, because that package
    is deprecated and emits a warning on import.
    """


def _library_wrapped_network_failure() -> Exception:
    """Build the exception supabase ACTUALLY raises when the host is unreachable.

    This matters more than it looks. The library catches httpx's ConnectError
    and re-raises its own error type, so an `isinstance(exc, httpx.TransportError)`
    check sees nothing and reports a network outage as a rejected password.

    Verified against the real library — the observed chain was:
        AuthRetryableError -> httpx.ConnectError -> socket.gaierror
    The only way to recognise it is to follow the chain.
    """
    try:
        try:
            raise httpx.ConnectError("[Errno 11001] getaddrinfo failed")
        except httpx.ConnectError as inner:
            raise _LibraryWrappedError("[Errno 11001] getaddrinfo failed") from inner
    except _LibraryWrappedError as outer:
        return outer


# Errors that mean "the network or the service is down", not "bad credentials".
INFRASTRUCTURE_ERRORS = [
    pytest.param(httpx.ConnectError("[Errno 11001] getaddrinfo failed"), id="dns-failure"),
    pytest.param(httpx.ReadTimeout("timed out"), id="timeout"),
    pytest.param(OSError("[Errno 11001] getaddrinfo failed"), id="socket-error"),
    pytest.param(_library_wrapped_network_failure(), id="library-wrapped"),
]

GOOD_CREDENTIALS = {"email": "someone@example.com", "password": "correct-horse-battery"}


@pytest.mark.parametrize("exc", INFRASTRUCTURE_ERRORS)
def test_login_reports_503_when_supabase_is_unreachable(client, failing_supabase, exc):
    failing_supabase(exc)

    response = client.post("/v1/auth/login", json=GOOD_CREDENTIALS)

    assert response.status_code == 503, (
        "An unreachable Supabase must not be reported as bad credentials — "
        f"got {response.status_code} with detail {response.json().get('detail')!r}"
    )


@pytest.mark.parametrize("exc", INFRASTRUCTURE_ERRORS)
def test_signup_reports_503_when_supabase_is_unreachable(client, failing_supabase, exc):
    failing_supabase(exc)

    response = client.post("/v1/auth/signup", json=GOOD_CREDENTIALS)

    assert response.status_code == 503


@pytest.mark.parametrize("exc", INFRASTRUCTURE_ERRORS)
def test_refresh_reports_503_when_supabase_is_unreachable(client, failing_supabase, exc):
    failing_supabase(exc)

    response = client.post("/v1/auth/refresh", json={"refresh_token": "any-token"})

    assert response.status_code == 503


@pytest.mark.parametrize("exc", INFRASTRUCTURE_ERRORS)
def test_me_reports_503_when_supabase_is_unreachable(client, failing_supabase, exc):
    failing_supabase(exc)

    response = client.get("/v1/auth/me", headers={"Authorization": "Bearer any-token"})

    assert response.status_code == 503


def test_login_still_returns_401_when_credentials_are_genuinely_rejected(
    client, failing_supabase
):
    """Guard: the 503 change must not swallow real credential rejections."""
    failing_supabase(Exception("Invalid login credentials"))

    response = client.post("/v1/auth/login", json=GOOD_CREDENTIALS)

    assert response.status_code == 401


def test_signup_does_not_leak_internal_error_text(client, failing_supabase):
    """Whatever the underlying library says must not be handed to the caller.

    Signup used to return `detail=str(exc)`, which sent raw internals to the
    client — a real response observed in verification was
    `{"detail": "[Errno 11001] getaddrinfo failed"}`.
    """
    secret_internals = "connection to 10.1.2.3:5432 failed: FATAL password authentication"
    failing_supabase(Exception(secret_internals))

    response = client.post("/v1/auth/signup", json=GOOD_CREDENTIALS)

    detail = str(response.json().get("detail"))
    assert secret_internals not in detail, f"internal error text leaked to client: {detail!r}"
    assert "10.1.2.3" not in detail
    assert detail, "there should still be *some* message for the caller"
