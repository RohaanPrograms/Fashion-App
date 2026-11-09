"""Request/response models for the auth endpoints."""

from pydantic import BaseModel, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Trade a refresh token for a fresh access token."""

    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: EmailStr | None = None
    # Guest accounts made by anonymous sign-in. The app (Phase 3) uses this to
    # offer "save your wardrobe with an email".
    is_anonymous: bool = False

    @field_validator("email", mode="before")
    @classmethod
    def _blank_email_means_none(cls, value):
        # Supabase gives guest accounts an empty-string email, which is not a
        # valid address. Treat it as "no email" instead of failing the request.
        return value or None


class Session(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int | None = None


class AuthResponse(BaseModel):
    user: UserOut
    session: Session | None = None
