"""Supabase client factories.

Two clients:
- anon client: used for user-facing auth flows (signup/login). Honours RLS.
- service client: server-side privileged access (bypasses RLS). Use sparingly.

Clients are created lazily so the app can boot without credentials during
early development.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_anon_client() -> Client:
    settings = get_settings()
    if not settings.supabase_configured:
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY "
            "in your .env file."
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


@lru_cache
def get_service_client() -> Client:
    settings = get_settings()
    if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
        raise RuntimeError(
            "Supabase service client not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in your .env file."
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
