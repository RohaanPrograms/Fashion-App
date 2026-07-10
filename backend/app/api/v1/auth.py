"""Auth endpoints — thin wrappers over Supabase Auth.

POST /v1/auth/signup  — create account
POST /v1/auth/login   — email/password login
GET  /v1/auth/me      — current user (requires Bearer token)
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.supabase_client import get_anon_client
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    Session,
    SignupRequest,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


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
        user=UserOut(id=user.id, email=user.email),
        session=session,
    )


def _client_or_503():
    try:
        return get_anon_client()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest) -> AuthResponse:
    client = _client_or_503()
    try:
        result = client.auth.sign_up(
            {"email": body.email, "password": body.password}
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc
    return _to_auth_response(result)


@router.get("/me", response_model=UserOut)
def me(current_user: UserOut = Depends(get_current_user)) -> UserOut:
    return current_user
