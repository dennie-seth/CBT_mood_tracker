from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from urllib.parse import quote

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    bot_token: str = Field(alias="BOT_TOKEN")

    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-haiku-4-5-20251001", alias="ANTHROPIC_MODEL"
    )
    ai_max_tool_iterations: int = Field(default=8, alias="AI_MAX_TOOL_ITERATIONS")

    # NoDecode: pydantic-settings would otherwise try to JSON-decode the env value
    # before our validator runs. We want raw CSV strings.
    allowed_telegram_ids: Annotated[frozenset[int], NoDecode] = Field(alias="ALLOWED_TELEGRAM_IDS")

    fernet_keys: Annotated[tuple[str, ...], NoDecode] = Field(alias="FERNET_KEYS")

    # Single source of truth for the Postgres credentials. `db_url` is composed
    # from these (see `db_url` below), which keeps the password edited in
    # exactly one place — `POSTGRES_PASSWORD`. The Postgres image reads the
    # same env vars at initdb time, so cluster and client always agree.
    postgres_user: str = Field(alias="POSTGRES_USER")
    postgres_password: str = Field(alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(alias="POSTGRES_DB")
    postgres_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    default_timezone: str = Field(default="UTC", alias="DEFAULT_TIMEZONE")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def db_url(self) -> str:
        """asyncpg URL with user/password URL-encoded so passwords containing
        `&`, `@`, `:`, etc. don't break parsing."""
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @field_validator("allowed_telegram_ids", mode="before")
    @classmethod
    def _parse_ids(cls, v: object) -> frozenset[int]:
        if isinstance(v, str):
            return frozenset(int(x.strip()) for x in v.split(",") if x.strip())
        if isinstance(v, (list, tuple, set, frozenset)):
            return frozenset(int(x) for x in v)
        raise ValueError("ALLOWED_TELEGRAM_IDS must be a CSV string of integers")

    @field_validator("fernet_keys", mode="before")
    @classmethod
    def _parse_keys(cls, v: object) -> tuple[str, ...]:
        if isinstance(v, str):
            keys = tuple(x.strip() for x in v.split(",") if x.strip())
            if not keys:
                raise ValueError("FERNET_KEYS must contain at least one key")
            return keys
        if isinstance(v, (list, tuple)):
            return tuple(str(x) for x in v)
        raise ValueError("FERNET_KEYS must be a CSV string")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
