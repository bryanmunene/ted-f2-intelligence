from __future__ import annotations

import pytest

from app.config import Settings, validate_runtime_settings


def _build_settings(**overrides) -> Settings:
    baseline = {
        "env": "production",
        "secret_key": "strong-super-secret",
        "session_https_only": True,
        "auth_enabled": True,
        "auto_create_schema": False,
    }
    baseline.update(overrides)
    return Settings(_env_file=None, **baseline)


def test_production_rejects_default_secret_key() -> None:
    settings = _build_settings(secret_key="change-me")
    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        validate_runtime_settings(settings)


def test_production_rejects_insecure_cookie_transport() -> None:
    settings = _build_settings(session_https_only=False)
    with pytest.raises(ValueError, match="APP_SESSION_HTTPS_ONLY"):
        validate_runtime_settings(settings)


def test_production_rejects_disabled_auth() -> None:
    settings = _build_settings(auth_enabled=False)
    with pytest.raises(ValueError, match="APP_AUTH_ENABLED"):
        validate_runtime_settings(settings)


def test_production_rejects_auto_schema_creation() -> None:
    settings = _build_settings(auto_create_schema=True)
    with pytest.raises(ValueError, match="APP_AUTO_CREATE_SCHEMA"):
        validate_runtime_settings(settings)


def test_production_with_secure_settings_is_valid() -> None:
    settings = _build_settings()
    validate_runtime_settings(settings)
