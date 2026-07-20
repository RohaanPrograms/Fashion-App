"""Application configuration.

Loads settings from environment variables (and a local .env file in dev).
Keep all environment access in this one place — never read os.environ
scattered across the codebase.

Which environment we run as is chosen by the APP_ENV variable:

    APP_ENV=dev      -> loads backend/.env         (default)
    APP_ENV=staging  -> loads backend/.env.staging
    APP_ENV=prod     -> loads backend/.env.prod

Examples:
    # Windows PowerShell
    $env:APP_ENV = "staging"; python -m uvicorn app.main:app
    # macOS/Linux
    APP_ENV=prod uvicorn app.main:app
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# APP_ENV value -> which .env file to load for that environment.
ENV_FILES: dict[str, str] = {
    "dev": ".env",
    "staging": ".env.staging",
    "prod": ".env.prod",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # env_file is chosen per-environment in get_settings() below.
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime environment: dev | staging | prod
    ENVIRONMENT: str = "dev"

    # Comma-separated allowed CORS origins. "*" allows all (dev only).
    CORS_ORIGINS: str = "*"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Later phases — present so the app boots even when unset.
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX: str = ""
    REPLICATE_API_TOKEN: str = ""
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_ANON_KEY)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton.

    Reads APP_ENV to decide which .env file to load, then applies a couple of
    safety checks so a misconfigured staging/prod process fails loudly at
    startup instead of silently running with unsafe defaults.
    """
    app_env = os.getenv("APP_ENV", "dev").strip().lower()
    if app_env not in ENV_FILES:
        raise ValueError(
            f"APP_ENV must be one of {list(ENV_FILES)}, got {app_env!r}"
        )

    settings = Settings(_env_file=ENV_FILES[app_env])

    # APP_ENV is the single source of truth for which environment we're in,
    # so make ENVIRONMENT match it no matter what the .env file said.
    settings.ENVIRONMENT = app_env

    # Guardrail: a wildcard CORS origin is fine in dev but dangerous in
    # staging/prod, where it would let any website call the API on a user's
    # behalf. Refuse to boot rather than ship that by accident.
    if app_env != "dev" and "*" in settings.cors_origins_list:
        raise ValueError(
            "CORS_ORIGINS cannot be '*' outside dev - "
            f"set explicit origins in {ENV_FILES[app_env]}."
        )

    return settings
