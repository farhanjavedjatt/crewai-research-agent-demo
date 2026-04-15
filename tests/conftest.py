"""Shared pytest fixtures.

Every test runs against mocked Supabase + LLM calls — the suite never touches
the network.
"""

from __future__ import annotations

import os
from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def _stub_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Provide the minimum env the settings module needs to load."""
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon-test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    # Reset the settings cache so each test sees the stubbed env.
    import research_crew.settings as settings_mod

    settings_mod.get_settings.cache_clear()
    settings_mod.settings = settings_mod.get_settings()
    yield
    settings_mod.get_settings.cache_clear()


@pytest.fixture
def no_supabase_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force any accidental Supabase client construction to fail loudly."""

    def _explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Tests must not hit Supabase.")

    monkeypatch.setattr(
        "research_crew.integrations.supabase_client.create_client", _explode
    )
