"""Auth endpoints — thin wrappers over Supabase Auth.

POST /v1/auth/signup  — create account
POST /v1/auth/login   — email/password login
POST /v1/auth/refresh — trade a refresh token for a fresh access token
POST /v1/auth/anonymous — start a guest session (no email)
POST /v1/auth/upgrade/start  — email a code to save a guest's account
POST /v1/auth/upgrade/verify — the code turns the guest into a normal account (same id)
POST /v1/auth/password       — set the password once the email is verified
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

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import get_bearer_token, get_current_user
from app.core import gotrue
from app.core.config import get_settings
from app.core.errors import UNAVAILABLE_DETAIL, is_infrastructure_error, log_upstream_failure
from app.core.rate_limit import RateLimiter, client_ip
from app.core.supabase_client import get_anon_client, get_service_client
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    PasswordRequest,
    RefreshRequest,
    Session,
    SignupRequest,
    UpgradeStartOut,
    UpgradeStartRequest,
    UpgradeVerifyRequest,
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


def _service_or_503():
    try:
        return get_service_client()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


def _auth_call(operation: str, call, refusals: dict[int, tuple[int, str]], fallback: str):
    """Run a gotrue call; turn every failure into a fixed, hand-written error.

    refusals maps Supabase's HTTP status to (our status, our message). Any
    other refusal -> 400 with `fallback`. Unreachable or 5xx -> 503.
    Supabase's own text only ever goes to the logs.
    """
    try:
        return call()
    except RuntimeError as exc:  # Supabase not configured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except gotrue.GoTrueError as exc:
        log_upstream_failure(operation, exc)
        if exc.status in refusals:
            code, detail = refusals[exc.status]
            raise HTTPException(status_code=code, detail=detail) from exc
        if exc.status >= 500:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE_DETAIL
            ) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=fallback) from exc
    except Exception as exc:  # noqa: BLE001
        log_upstream_failure(operation, exc)
        if is_infrastructure_error(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE_DETAIL
            ) from exc
        raise


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


WRONG_CODE = "That code is wrong or has expired. Ask for a new code."


@router.post(
    "/upgrade/start", response_model=UpgradeStartOut, status_code=status.HTTP_202_ACCEPTED
)
def upgrade_start(
    body: UpgradeStartRequest,
    current_user: UserOut = Depends(get_current_user),
    token: str = Depends(get_bearer_token),
) -> UpgradeStartOut:
    """Step 1 of saving a guest's account: Supabase emails a one-time code
    (its length is a Supabase setting; 8 digits on this project).

    The account keeps its id through all three steps, so every swipe, like
    and outfit stays with it.

    "Is this a guest?" is answered by the database, not the token: a token
    issued before an upgrade still says "guest" until it expires.
    """
    admin = _service_or_503()
    try:
        stored = admin.auth.admin.get_user_by_id(current_user.id).user
    except Exception as exc:  # noqa: BLE001
        _fail(
            "upgrade lookup",
            exc,
            auth_status=status.HTTP_401_UNAUTHORIZED,
            auth_detail="Invalid or expired token",
        )
    if not getattr(stored, "is_anonymous", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This account already has an email."
        )

    _auth_call(
        "upgrade start",
        lambda: gotrue.request_email_change(token, body.email),
        refusals={
            422: (
                status.HTTP_409_CONFLICT,
                "That email is already registered. Log in instead.",
            ),
            429: (
                status.HTTP_429_TOO_MANY_REQUESTS,
                "A code was sent very recently. Wait a minute, then ask again.",
            ),
        },
        fallback="Couldn't send a code to that address.",
    )
    return UpgradeStartOut(email=body.email)


@router.post("/upgrade/verify", response_model=AuthResponse)
def upgrade_verify(
    body: UpgradeVerifyRequest, current_user: UserOut = Depends(get_current_user)
) -> AuthResponse:
    """Step 2: the emailed code turns the guest into a normal account.

    Same id, so everything is kept. Returns a fresh session, because the old
    token still says "guest".
    """
    data = _auth_call(
        "upgrade verify",
        lambda: gotrue.verify_email_change(body.email, body.code),
        refusals={
            401: (status.HTTP_400_BAD_REQUEST, WRONG_CODE),
            403: (status.HTTP_400_BAD_REQUEST, WRONG_CODE),
        },
        fallback=WRONG_CODE,
    )
    user = data.get("user") or {}
    if user.get("id") != current_user.id:
        # Can't happen through the app (the code is sent to the caller's own
        # pending address), but never hand one account's session to another.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="That code belongs to another account."
        )
    return AuthResponse(
        user=UserOut(
            id=user["id"],
            email=user.get("email"),
            is_anonymous=bool(user.get("is_anonymous", False)),
        ),
        session=Session(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data.get("expires_in"),
        ),
    )


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(
    body: PasswordRequest,
    current_user: UserOut = Depends(get_current_user),
    token: str = Depends(get_bearer_token),
) -> Response:
    """Step 3: give the now-verified account a password, so it can log in.

    Separate from step 2 so that if it fails, the app retries just this,
    with the fresh session it already holds.
    """
    if current_user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Confirm your email first."
        )
    _auth_call(
        "set password",
        lambda: gotrue.set_password(token, body.password),
        refusals={},
        fallback="That password was refused. Try a longer or less common one.",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
