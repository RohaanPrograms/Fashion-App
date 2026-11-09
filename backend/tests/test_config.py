"""Railway provides settings as environment variables, not a .env.prod file.
These tests document that this works, and that production still refuses an
open CORS setting."""

import pytest

from app.core import config


@pytest.fixture
def fresh_settings(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no .env / .env.prod here
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def test_production_reads_settings_from_environment_variables(monkeypatch, fresh_settings):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("CLIENT_IP_HEADER", "X-Real-IP")

    settings = config.get_settings()

    assert settings.ENVIRONMENT == "prod"
    assert settings.SUPABASE_URL == "https://example.supabase.co"
    assert settings.cors_origins_list == ["https://app.example.com"]
    assert settings.CLIENT_IP_HEADER == "X-Real-IP"


def test_production_refuses_cors_open_to_every_website(monkeypatch, fresh_settings):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("CORS_ORIGINS", "*")

    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        config.get_settings()


def test_no_proxy_header_is_trusted_unless_configured(monkeypatch, fresh_settings):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    monkeypatch.delenv("CLIENT_IP_HEADER", raising=False)

    assert config.get_settings().CLIENT_IP_HEADER == ""
