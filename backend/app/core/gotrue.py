"""Calls to Supabase Auth made AS the signed-in user.

supabase-py's update_user() acts on a session stored inside the client, and
our client is one shared object for every request, so storing a visitor's
session in it could leak between visitors. These few calls go straight to
Supabase Auth's HTTP API instead, passing the user's own token each time.
(Supabase Auth is a program called GoTrue, hence the module name.)

Refusals become GoTrueError (HTTP status + Supabase's machine-readable code).
Network failures are left as httpx's own errors, so the API's usual
"unreachable -> 503" handling recognises them.
"""

import httpx

from app.core.config import get_settings

TIMEOUT_SECONDS = 10.0


class GoTrueError(Exception):
    """Supabase Auth answered, and the answer was no."""

    def __init__(self, status: int, code: str | None, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _send(method: str, url: str, headers: dict, body: dict) -> httpx.Response:
    """The only function here that touches the network (tests replace it)."""
    return httpx.request(method, url, headers=headers, json=body, timeout=TIMEOUT_SECONDS)


def _call(method: str, path: str, body: dict, token: str | None = None) -> dict:
    settings = get_settings()
    if not settings.supabase_configured:
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY in your .env file."
        )
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1{path}"
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        # Calls made "as nobody" (checking a code) use the public anon key.
        "Authorization": f"Bearer {token or settings.SUPABASE_ANON_KEY}",
    }
    response = _send(method, url, headers, body)
    if response.is_success:
        return response.json() if response.content else {}
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    raise GoTrueError(
        response.status_code,
        data.get("error_code"),
        str(
            data.get("msg")
            or data.get("message")
            or data.get("error_description")
            or response.reason_phrase
        ),
    )


def request_email_change(access_token: str, email: str) -> None:
    """Ask Supabase to email a code that confirms `email` for this account."""
    _call("PUT", "/user", {"email": email}, token=access_token)


def verify_email_change(email: str, code: str) -> dict:
    """Check the emailed code. Returns Supabase's session JSON (tokens + user)."""
    return _call("POST", "/verify", {"type": "email_change", "email": email, "token": code})


def set_password(access_token: str, password: str) -> None:
    _call("PUT", "/user", {"password": password}, token=access_token)
