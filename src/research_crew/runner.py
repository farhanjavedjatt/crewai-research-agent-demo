"""High-level runner that glues the crew to Supabase.

The runner is the single entry point used by both the CLI and the Streamlit
UI. It owns the concerns that are cross-cutting to both surfaces:

- creating / completing a Supabase session row
- persisting each agent's output as an artifact
- surfacing per-task progress to the caller via an optional callback
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from crewai.tasks.task_output import TaskOutput

from research_crew.crew import ResearchCrew
from research_crew.integrations import ResearchStore, SessionRecord, get_store
from research_crew.logging_conf import get_logger
from research_crew.settings import settings

logger = get_logger(__name__)

# A progress event surfaced to UI layers. Kept intentionally minimal so
# Streamlit / CLI / HTTP can all consume the same shape.
ProgressCallback = Callable[["ProgressEvent"], None]


@dataclass(slots=True)
class ProgressEvent:
    sequence: int
    agent_role: str
    task_name: str
    output: str


@dataclass(slots=True)
class RunResult:
    session: SessionRecord
    report_markdown: str
    duration_seconds: float


def run_research(
    query: str,
    *,
    on_progress: ProgressCallback | None = None,
    store: ResearchStore | None = None,
) -> RunResult:
    """Kick off the crew, persist results, and return the final brief.

    Args:
        query: The user's research question.
        on_progress: Optional callback invoked as each task completes.
        store: Optional :class:`ResearchStore` (injected in tests).
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")

    settings.export_llm_env()
    store = store or get_store()

    session = store.create_session(query=query, model=settings.model_name)
    logger.info("Starting crew for session %s", session.id)

    started = time.perf_counter()
    sequence = 0

    def _task_callback(output: TaskOutput) -> None:
        nonlocal sequence
        sequence += 1
        agent_role = (getattr(output, "agent", None) or "unknown").strip()
        task_name = (getattr(output, "name", None) or f"task_{sequence}").strip()
        content = str(output.raw) if getattr(output, "raw", None) else str(output)
        try:
            store.record_artifact(
                session.id,
                agent_role=agent_role,
                task_name=task_name,
                content=content,
                sequence=sequence,
            )
        except Exception:
            # Persistence failures must never break the crew run.
            logger.exception("Failed to persist artifact for %s", task_name)
        if on_progress is not None:
            try:
                on_progress(
                    ProgressEvent(
                        sequence=sequence,
                        agent_role=agent_role,
                        task_name=task_name,
                        output=content,
                    )
                )
            except Exception:
                logger.exception("on_progress callback raised; continuing.")

    try:
        crew_instance = ResearchCrew().crew()
        # Inject the per-task callback at run time so the definition in crew.py
        # stays declarative.
        for t in crew_instance.tasks:
            t.callback = _task_callback

        result = crew_instance.kickoff(inputs={"query": query})
        report_markdown = str(result.raw if hasattr(result, "raw") else result)
        duration = time.perf_counter() - started

        store.complete_session(
            session.id,
            report_markdown=report_markdown,
            duration_seconds=duration,
            metadata={
                "model": settings.model_name,
                "tasks_completed": sequence,
            },
        )
        return RunResult(
            session=store.get_session(session.id) or session,
            report_markdown=report_markdown,
            duration_seconds=duration,
        )

    except Exception as exc:
        store.fail_session(session.id, str(exc))
        raise
