"""Unit tests for api.config.Settings."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def no_env_file(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Run from a directory without a .env file.

    Settings declares env_file=".env", so default-value tests must not be
    executed from the project root where .env exists — otherwise the file
    silently overrides the defaults that monkeypatch.delenv cannot remove.
    """
    monkeypatch.chdir(tmp_path)


class TestSettingsDefaults:
    """Verify Settings loads with sensible defaults when no .env is present."""

    def test_default_app_name(self, no_env_file, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("APP_NAME", raising=False)
        from api.config import Settings
        s = Settings()
        assert s.APP_NAME == "TFT Agent Set 17"

    def test_default_db_path(self, no_env_file, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("DB_PATH", raising=False)
        from api.config import Settings
        s = Settings()
        assert s.DB_PATH == "data/tft.db"

    def test_default_port(self, no_env_file, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("PORT", raising=False)
        from api.config import Settings
        s = Settings()
        assert s.PORT == 8002

    def test_default_jwt_algorithm(self, no_env_file, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("JWT_ALGORITHM", raising=False)
        from api.config import Settings
        s = Settings()
        assert s.JWT_ALGORITHM == "HS256"


class TestSettingsEnvOverride:
    """Verify Settings reads values from environment variables."""

    def test_override_db_path(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
        from api.config import Settings
        s = Settings()
        assert s.DB_PATH == "/tmp/custom.db"

    def test_override_port(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("PORT", "9999")
        from api.config import Settings
        s = Settings()
        assert s.PORT == 9999

    def test_override_debug(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DEBUG", "false")
        from api.config import Settings
        s = Settings()
        assert s.DEBUG is False


class TestJWTSecret:
    """Verify JWT_SECRET can be set and read."""

    def test_default_secret(self, no_env_file, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("JWT_SECRET", raising=False)
        from api.config import Settings
        s = Settings()
        assert s.JWT_SECRET == "dev-change-me"

    def test_custom_secret(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("JWT_SECRET", "super-secret-value")
        from api.config import Settings
        s = Settings()
        assert s.JWT_SECRET == "super-secret-value"

    def test_secret_is_string(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("JWT_SECRET", "12345")
        from api.config import Settings
        s = Settings()
        assert isinstance(s.JWT_SECRET, str)
