"""Auth endpoints — thin wrappers over Supabase Auth.

POST /v1/auth/signup  — create account
POST /v1/auth/login   — email/password login
POST /v1/auth/refresh — trade a refresh token for a fresh access token
POST /v1/auth/anonymous — start a guest session (no email)
GET  /v1/auth/me      — current user (requires Bearer token)

Two tokens are in play. The *access token* is what the app sends on every
request; Supabase expires it after about an hour so a stolen one is only
briefly useful. The *refresh token* is long-lived and does one job: exchange
itself for a new access token, which is what keeps a user signed in.

Every call here passes its token explicitly. The Supabase client is a shared
singleton, so we never rely on whatever session it happens to hold internally.
"""

import math
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.errors import UNAVAILABLE_DETAIL, is_infrastructure_error, log_upstream_failure
from app.core.rate_limit import RateLimiter, client_ip
from app.core.supabase_client import get_anon_client
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    Session,
    SignupRequest,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# New guest accounts per IP address per hour. Generous enough for an office of
# people trying the demo; tight enough that one script cannot create hundreds.
GUEST_SIGNINS_PER_HOUR = 5
guest_signins = RateLimiter(GUEST_SIGNINS_PER_HOUR, window_seconds=3600)


def _to_auth_response(result) -> AuthResponse:
    """Map a supabase-py auth result into our response schema."""
    user = result.user
    session = None
    if getattr(result, "session", None) is not None:
        s = result.session
        session = Session(
            access_token=s.access_token,
            refresh_token=s.refresh_token,
            expires_in=getattr(s, "expires_in", None),
        )
    return AuthResponse(
        user=UserOut(
            id=user.id, email=user.email, is_anonymous=bool(getattr(user, "is_anonymous", False))
        ),
        session=session,
    )


def _client_or_503():
    try:
        return get_anon_client()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


def _fail(
    operation: str, exc: Exception, *, auth_status: int, auth_detail: str
) -> NoReturn:
    """Turn an exception from Supabase into the right HTTP error.

    Unreachable service -> 503 with a neutral message.
    Service said no     -> the endpoint's own auth status and message.

    Either way the caller gets a fixed, hand-written string. The exception's own
    text goes to the logs only: it can contain hostnames, ports and internal
    failure detail, and it was previously returned straight to the client.
    """
    log_upstream_failure(operation, exc)
    if is_infrastructure_error(exc):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE_DETAIL
        ) from exc
    raise HTTPException(status_code=auth_status, detail=auth_detail) from exc


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest) -> AuthResponse:
    client = _client_or_503()
    try:
        result = client.auth.sign_up(
            {"email": body.email, "password": body.password}
        )
    except Exception as exc:  # noqa: BLE001
        _fail(
            "signup",
            exc,
            auth_status=status.HTTP_400_BAD_REQUEST,
            auth_detail=(
                "Could not create the account. The email may already be "
                "registered, or the password may not meet requirements."
            ),
        )
    if result.user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Signup failed"
        )
    return _to_auth_response(result)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest) -> AuthResponse:
    client = _client_or_503()
    try:
        result = client.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as exc:  # noqa: BLE001
        _fail(
            "login",
            exc,
            auth_status=status.HTTP_401_UNAUTHORIZED,
            auth_detail="Invalid email or password",
        )
    return _to_auth_response(result)


@router.post("/anonymous", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def anonymous(request: Request) -> AuthResponse:
    """Start a guest session: a real account with no email or password.

    Lets a visitor start swiping straight away. Everything downstream is the
    same: the token passes get_current_user and swipes save under its user id.

    Limited to GUEST_SIGNINS_PER_HOUR per IP address, checked before Supabase
    is asked, so hammering this endpoint costs Supabase nothing.

    Needs "Allow anonymous sign-ins" switched on in Supabase. When it is off,
    Supabase refuses and this returns 503 — a server setting, not the caller's
    fault, so not a 4xx.
    """
    wait = guest_signins.hit(client_ip(request, get_settings().CLIENT_IP_HEADER))
    if wait is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many guest sign-ins from your network. Please try again later.",
            headers={"Retry-After": str(max(1, math.ceil(wait)))},
        )
    client = _client_or_503()
    try:
        result = client.auth.sign_in_anonymously()
    except Exception as exc:  # noqa: BLE001
        _fail(
            "anonymous sign-in",
            exc,
            auth_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            auth_detail="Guest sign-in is not available right now.",
        )
    if result.user is None or getattr(result, "session", None) is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Guest sign-in is not available right now.",
        )
    return _to_auth_response(result)


@router.post("/refresh", response_model=AuthResponse)
def refresh(body: RefreshRequest) -> AuthResponse:
    """Issue a new access token from a still-valid refresh token.

    A 401 here means the refresh token is expired or revoked (signed out
    elsewhere, password changed) — the client should treat it as a real
    logout and send the user back to the login screen.
    """
    client = _client_or_503()
    try:
        result = client.auth.refresh_session(body.refresh_token)
    except Exception as exc:  # noqa: BLE001
        _fail(
            "refresh",
            exc,
            auth_status=status.HTTP_401_UNAUTHORIZED,
            auth_detail="Invalid or expired refresh token",
        )
    if result.user is None or getattr(result, "session", None) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return _to_auth_response(result)


@router.get("/me", response_model=UserOut)
def me(current_user: UserOut = Depends(get_current_user)) -> UserOut:
    return current_user
