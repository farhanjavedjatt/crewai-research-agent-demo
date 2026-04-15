"""Centralised configuration loaded from environment variables.

The `NEXT_PUBLIC_SUPABASE_*` prefixes are kept to mirror the frontend dashboard
that already consumes Supabase — this keeps a single source of truth across
the stack.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed runtime configuration."""

    # --- LLM ----------------------------------------------------------------
    model_name: str = Field(default="openai/gpt-4o-mini")
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    # --- Supabase -----------------------------------------------------------
    supabase_url: str = Field(alias="NEXT_PUBLIC_SUPABASE_URL")
    supabase_anon_key: SecretStr = Field(alias="NEXT_PUBLIC_SUPABASE_ANON_KEY")
    supabase_service_role_key: SecretStr = Field(alias="SUPABASE_SERVICE_ROLE_KEY")

    # --- Tools --------------------------------------------------------------
    serper_api_key: SecretStr | None = None

    # --- Runtime ------------------------------------------------------------
    log_level: str = "INFO"
    history_limit: int = 25

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("supabase_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def has_serper(self) -> bool:
        return self.serper_api_key is not None and bool(
            self.serper_api_key.get_secret_value()
        )

    def export_llm_env(self) -> None:
        """Export LLM credentials into the process env.

        CrewAI / LiteLLM look up provider keys via well-known env var names.
        Keeping this in one place avoids accidental leaks elsewhere.
        """
        import os

        if self.openai_api_key:
            os.environ.setdefault("OPENAI_API_KEY", self.openai_api_key.get_secret_value())
        if self.anthropic_api_key:
            os.environ.setdefault(
                "ANTHROPIC_API_KEY", self.anthropic_api_key.get_secret_value()
            )
        if self.has_serper and self.serper_api_key is not None:
            os.environ.setdefault("SERPER_API_KEY", self.serper_api_key.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
