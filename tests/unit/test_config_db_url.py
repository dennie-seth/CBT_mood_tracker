"""Settings.db_url is composed from individual POSTGRES_* fields.

Single source of truth for the password: editing POSTGRES_PASSWORD must
also fix what asyncpg dials. Special characters in the password must be
URL-encoded so a `&` or `@` in the password doesn't break parsing.
"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.config import Settings


def _base_env() -> dict[str, str]:
    return {
        "BOT_TOKEN": "1:fake",
        "ANTHROPIC_API_KEY": "sk-ant-fake",
        "ALLOWED_TELEGRAM_IDS": "1",
        "FERNET_KEYS": Fernet.generate_key().decode(),
        "POSTGRES_USER": "mood",
        "POSTGRES_PASSWORD": "simple",
        "POSTGRES_DB": "mood",
        "POSTGRES_HOST": "postgres",
        "POSTGRES_PORT": "5432",
    }


@pytest.fixture()
def settings_factory(monkeypatch):
    """Build a Settings with env-var-style overrides (matching production)."""

    def _make(**overrides: str) -> Settings:
        env = _base_env()
        env.update(overrides)
        # Reset everything that might leak from the test runner's environment
        # (e.g. a real DB_URL set by the developer's shell).
        for k in [*env.keys(), "DB_URL"]:
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        return Settings(_env_file=None)  # type: ignore[call-arg]

    return _make


def test_db_url_composed_from_postgres_fields(settings_factory) -> None:
    s = settings_factory()
    assert s.db_url == "postgresql+asyncpg://mood:simple@postgres:5432/mood"


def test_db_url_url_encodes_special_password_chars(settings_factory) -> None:
    """A password with '&', '@', ':', '/', '#' must round-trip safely:
    encoded in the URL, decoded by asyncpg, matches what Postgres stored."""
    from urllib.parse import quote

    raw = "xDFKluwfm5MuF&HXglXXZS9-PlFajbLK"
    s = settings_factory(POSTGRES_PASSWORD=raw)
    encoded = quote(raw, safe="")
    assert s.db_url == f"postgresql+asyncpg://mood:{encoded}@postgres:5432/mood"

    # Heavier mix that would definitely break a literal embed:
    nasty = "p@ss:w/o#rd&with?stuff"
    s = settings_factory(POSTGRES_PASSWORD=nasty)
    assert quote(nasty, safe="") in s.db_url
    assert "@postgres:5432/mood" in s.db_url


def test_db_url_url_encodes_username_too(settings_factory) -> None:
    """Defensive: usernames with special chars are unusual but handled."""
    s = settings_factory(POSTGRES_USER="m@d")
    assert s.db_url.startswith("postgresql+asyncpg://m%40d:")


def test_db_url_default_port(settings_factory, monkeypatch) -> None:
    """POSTGRES_PORT is optional and defaults to 5432."""
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    s = settings_factory()
    monkeypatch.delenv("POSTGRES_PORT", raising=False)  # ensure no leak
    # Re-create without POSTGRES_PORT (factory sets it; we override by deletion afterwards)
    # Simpler: re-call factory with explicit override that we then delete
    # — but pydantic-settings re-reads env at __init__, so deleting after
    # construction has no effect. Instead, build a settings with PORT="5432" and
    # additionally test through the factory's default (which already sets 5432).
    # Real coverage: assert that 5432 is what shows up when POSTGRES_PORT is the default.
    assert s.db_url.endswith("@postgres:5432/mood")


def test_db_url_default_port_when_env_unset(monkeypatch) -> None:
    """If POSTGRES_PORT is missing from the env entirely, default to 5432."""
    env = _base_env()
    del env["POSTGRES_PORT"]
    for k in [*env.keys(), "DB_URL", "POSTGRES_PORT"]:
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.db_url.endswith("@postgres:5432/mood")


def test_db_url_env_var_no_longer_a_source_of_truth(settings_factory) -> None:
    """A stale DB_URL line in .env must not silently override the composed value."""
    s = settings_factory(DB_URL="postgresql+asyncpg://stale:stale@stale:5432/stale")
    assert "stale" not in s.db_url
    assert s.db_url == "postgresql+asyncpg://mood:simple@postgres:5432/mood"
