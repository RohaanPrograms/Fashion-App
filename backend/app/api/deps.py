"""Shared FastAPI dependencies."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jwt import PyJWTError

from app.core.config import get_settings  # noqa: F401 — patched in tests
from app.core.errors import is_infrastructure_error, log_upstream_failure
from app.core.security import decode_access_token, uses_local_verification
from app.core.supabase_client import get_anon_client
from app.schemas.auth import UserOut

_bearer = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> UserOut:
    """Resolve the Supabase user from the Bearer access token.

    Raises 401 if the token is missing or invalid.
    """
    token = credentials.credentials

    # Fast path: check the signature ourselves. No network, no Supabase quota.
    # Only taken when the configured secret has been confirmed to belong to this
    # project — see uses_local_verification() for why that check exists.
    if uses_local_verification():
        try:
            claims = decode_access_token(token)
        except PyJWTError as exc:
            # Expired, forged, tampered with, or malformed. Supabase would have
            # said no too; we just said it faster.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from exc
        return UserOut(id=claims["sub"], email=claims.get("email"))

    try:
        client = get_anon_client()
        response = client.auth.get_user(token)
    except RuntimeError as exc:  # Supabase not configured yet
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except Exception as exc:  # noqa: BLE001
        # An unreachable Supabase must not be reported as a bad token: the user
        # would be signed out of a perfectly valid session during an outage.
        log_upstream_failure("token validation", exc)
        if is_infrastructure_error(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "The authentication service is temporarily unavailable. "
                    "Please try again shortly."
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    user = getattr(response, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return UserOut(id=user.id, email=user.email)
