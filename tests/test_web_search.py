"""Web-search selection logic."""

from __future__ import annotations

import json
from typing import Any

import pytest

from research_crew.tools.web_search import DuckDuckGoSearchTool, build_web_search_tool


def test_selects_duckduckgo_by_default() -> None:
    tool = build_web_search_tool()
    assert isinstance(tool, DuckDuckGoSearchTool)
    assert tool.name == "web_search"


def test_duckduckgo_tool_returns_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeDDGS:
        def __enter__(self) -> "_FakeDDGS":
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def text(self, query: str, max_results: int = 6) -> list[dict[str, Any]]:
            assert query == "CrewAI"
            assert max_results == 3
            return [
                {"title": "A", "href": "https://a", "body": "body a"},
                {"title": "B", "href": "https://b", "body": "body b" * 200},
            ]

    import research_crew.tools.web_search as mod

    monkeypatch.setitem(__import__("sys").modules, "ddgs", type("M", (), {"DDGS": _FakeDDGS}))

    tool = DuckDuckGoSearchTool()
    raw = tool._run(query="CrewAI", max_results=3)
    parsed = json.loads(raw)
    assert len(parsed) == 2
    assert parsed[0]["title"] == "A"
    assert parsed[0]["href"] == "https://a"
    # body is truncated to 400 chars
    assert len(parsed[1]["body"]) <= 400
