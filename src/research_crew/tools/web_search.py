"""Web-search tool with a zero-config default and an optional upgrade path.

Selection order:

1. If ``SERPER_API_KEY`` is configured, use CrewAI's built-in
   :class:`SerperDevTool` — richer results, ~2,500 free searches/month.
2. Otherwise fall back to a DuckDuckGo-based tool that ships with the repo
   and requires no API key. Great for the demo; fine for low-volume prod.
"""

from __future__ import annotations

import json
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from research_crew.logging_conf import get_logger
from research_crew.settings import settings

logger = get_logger(__name__)


class _WebSearchInput(BaseModel):
    """Inputs shared by every web-search implementation."""

    query: str = Field(..., description="The search query. Be specific and concise.")
    max_results: int = Field(
        default=6,
        ge=1,
        le=15,
        description="Maximum number of results to return.",
    )


class DuckDuckGoSearchTool(BaseTool):
    """A zero-config web search tool backed by DuckDuckGo.

    Uses the maintained ``ddgs`` package (formerly ``duckduckgo-search``).
    Returns a compact JSON list the agent can reason over directly.
    """

    name: str = "web_search"
    description: str = (
        "Search the public web via DuckDuckGo and return a JSON list of "
        "{title, href, body} results. Use this for any factual lookup."
    )
    args_schema: type[BaseModel] = _WebSearchInput

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
        reraise=True,
    )
    def _run(self, query: str, max_results: int = 6) -> str:
        # Imported lazily so the package remains optional for tests.
        from ddgs import DDGS

        logger.info("web_search via DuckDuckGo: %s", query)
        with DDGS() as ddgs:
            results: list[dict[str, Any]] = list(
                ddgs.text(query, max_results=max_results)
            )

        trimmed = [
            {
                "title": r.get("title"),
                "href": r.get("href") or r.get("url"),
                "body": (r.get("body") or "")[:400],
            }
            for r in results
            if r.get("title")
        ]
        return json.dumps(trimmed, ensure_ascii=False)


def build_web_search_tool() -> BaseTool:
    """Return the best web-search tool available given current configuration."""
    if settings.has_serper:
        # Imported lazily because crewai_tools pulls in heavy deps.
        from crewai_tools import SerperDevTool

        logger.info("Using SerperDevTool (premium web search).")
        return SerperDevTool()

    logger.info("Using DuckDuckGo web search (no API key required).")
    return DuckDuckGoSearchTool()
