"""Application configuration.

Loads settings from environment variables (and a local .env file in dev).
Keep all environment access in this one place — never read os.environ
scattered across the codebase.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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
    """Cached settings singleton."""
    return Settings()
