"""Settings should load from env and expose typed accessors."""

from __future__ import annotations

import pytest

from research_crew.settings import Settings


def test_settings_load_from_env() -> None:
    s = Settings()  # type: ignore[call-arg]
    assert s.supabase_url == "https://example.supabase.co"
    assert s.supabase_anon_key.get_secret_value() == "anon-test"
    assert s.supabase_service_role_key.get_secret_value() == "service-test"
    assert s.model_name.startswith(("openai/", "anthropic/"))


def test_trailing_slash_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co/")
    s = Settings()  # type: ignore[call-arg]
    assert s.supabase_url == "https://example.supabase.co"


def test_has_serper_false_when_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    s = Settings()  # type: ignore[call-arg]
    assert s.has_serper is False


def test_has_serper_true_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPER_API_KEY", "serper-key-123")
    s = Settings()  # type: ignore[call-arg]
    assert s.has_serper is True
