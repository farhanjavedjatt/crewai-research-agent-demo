"""Streamlit UI for the Research Crew.

Run locally:
    streamlit run streamlit_app.py

Railway runs the same command via the Procfile. The server port comes from
the `PORT` env var (see Procfile / railway.json).

On Streamlit Community Cloud, secrets configured in the dashboard are exposed
via :data:`st.secrets`. The small ``_bootstrap_secrets`` helper below copies
them into :mod:`os.environ` so ``pydantic-settings`` picks them up — this keeps
a single config path across local / Railway / SCC.
"""

from __future__ import annotations

import os
import queue
import threading
from datetime import datetime
from typing import Any

import streamlit as st


def _bootstrap_secrets() -> None:
    """Promote ``st.secrets`` into ``os.environ`` (Streamlit Community Cloud).

    No-op locally (uses ``.env``) and on Railway (uses real env vars). Only
    scalar secrets at the top level are copied; nested sections are ignored.
    Existing env vars win — we never clobber values provided by the host.
    """
    try:
        secrets = st.secrets  # type: ignore[attr-defined]
    except Exception:
        return

    for key in list(secrets):  # iterate top-level keys safely
        try:
            value = secrets[key]
        except Exception:
            continue
        if isinstance(value, (str, int, float, bool)):
            os.environ.setdefault(key, str(value))


# Must run before anything imports `research_crew.settings`.
_bootstrap_secrets()

from research_crew.integrations import get_store  # noqa: E402
from research_crew.logging_conf import configure_logging  # noqa: E402
from research_crew.runner import ProgressEvent, RunResult, run_research  # noqa: E402
from research_crew.settings import settings  # noqa: E402

configure_logging()

AGENT_AVATARS: dict[str, str] = {
    "Senior Research Strategist": "🧭",
    "Principal Research Analyst": "🔎",
    "Insights Synthesist": "🧠",
    "Executive Research Writer": "✍️",
}

st.set_page_config(
    page_title="Research Crew — CrewAI Demo",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Sidebar: session history from Supabase --------------------------------


def _render_sidebar() -> None:
    st.sidebar.title("🛰️ Research Crew")
    st.sidebar.caption(
        "A multi-agent CrewAI demo: **plan → research → analyse → write**, "
        "backed by Supabase."
    )

    st.sidebar.divider()
    st.sidebar.subheader("Configuration")
    st.sidebar.markdown(f"**Model:** `{settings.model_name}`")
    st.sidebar.markdown(
        f"**Web search:** `{'Serper' if settings.has_serper else 'DuckDuckGo'}`"
    )

    st.sidebar.divider()
    st.sidebar.subheader("Recent sessions")

    try:
        store = get_store()
        sessions = store.list_recent_sessions(limit=settings.history_limit)
    except Exception as exc:  # Supabase misconfigured — show a gentle hint.
        st.sidebar.warning(f"Could not load history: {exc}")
        return

    if not sessions:
        st.sidebar.info("No past runs yet — kick one off on the right.")
        return

    for s in sessions:
        label_icon = {"completed": "✅", "running": "⏳", "failed": "❌"}.get(
            s.status, "•"
        )
        when = _format_when(s.created_at)
        preview = (s.query[:60] + "…") if len(s.query) > 60 else s.query
        if st.sidebar.button(
            f"{label_icon} {preview}\n\n*{when}*",
            key=f"session-{s.id}",
            use_container_width=True,
        ):
            st.session_state["viewing_session_id"] = s.id
            st.rerun()


def _format_when(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %H:%M")
    except ValueError:
        return iso


# --- Main surfaces ----------------------------------------------------------


def _render_history_view(session_id: str) -> None:
    store = get_store()
    session = store.get_session(session_id)
    if session is None:
        st.error("Session not found.")
        return

    top = st.container()
    with top:
        left, right = st.columns([5, 1])
        with left:
            st.markdown(f"### {session.query}")
            st.caption(
                f"Status: `{session.status}` · Model: `{session.model}` · "
                f"Duration: {session.duration_seconds or 0:.1f}s · "
                f"Created: {_format_when(session.created_at)}"
            )
        with right:
            if st.button("← New run", use_container_width=True):
                st.session_state.pop("viewing_session_id", None)
                st.rerun()

    artifacts = store.list_artifacts(session_id)
    if artifacts:
        st.subheader("Agent trace")
        for art in artifacts:
            avatar = AGENT_AVATARS.get(art["agent_role"], "🤖")
            with st.chat_message("assistant", avatar=avatar):
                st.markdown(
                    f"**{art['agent_role']}** · _{art['task_name']}_"
                )
                st.markdown(art["content"])

    if session.report_markdown:
        st.subheader("Final brief")
        st.markdown(session.report_markdown)
        st.download_button(
            "Download brief (.md)",
            data=session.report_markdown,
            file_name=f"research-{session.id[:8]}.md",
            mime="text/markdown",
            use_container_width=False,
        )


def _render_chat_view() -> None:
    st.title("What would you like the crew to research?")
    st.caption(
        "Try something like *“Competitive landscape for AI agent platforms in 2026”* "
        "or *“What are the most credible arguments for and against nuclear baseload in Europe?”*."
    )

    query = st.chat_input("Ask a research question…")
    if not query:
        return

    with st.chat_message("user", avatar="🧑"):
        st.markdown(query)

    events: queue.Queue[ProgressEvent | RunResult | Exception] = queue.Queue()

    def _runner() -> None:
        try:
            result = run_research(
                query,
                on_progress=lambda ev: events.put(ev),
            )
            events.put(result)
        except Exception as exc:  # noqa: BLE001
            events.put(exc)

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()

    _stream_events_to_ui(events, thread)


def _stream_events_to_ui(
    events: "queue.Queue[Any]", thread: threading.Thread
) -> None:
    current_status: Any = None
    progress_container = st.container()

    with progress_container:
        placeholder = st.status("🧭 Planning research approach…", expanded=True)
        current_status = placeholder

    while thread.is_alive() or not events.empty():
        try:
            ev = events.get(timeout=0.5)
        except queue.Empty:
            continue

        if isinstance(ev, ProgressEvent):
            avatar = AGENT_AVATARS.get(ev.agent_role, "🤖")
            # Close the previous in-progress status
            if current_status is not None:
                current_status.update(state="complete")
            current_status = st.status(
                f"{avatar}  **{ev.agent_role}** — {ev.task_name}", expanded=False
            )
            with current_status:
                st.markdown(ev.output)

        elif isinstance(ev, RunResult):
            if current_status is not None:
                current_status.update(state="complete")
            st.success(
                f"Done in {ev.duration_seconds:.1f}s · session `{ev.session.id[:8]}`"
            )
            with st.chat_message("assistant", avatar="📄"):
                st.markdown(ev.report_markdown)
            st.download_button(
                "Download brief (.md)",
                data=ev.report_markdown,
                file_name=f"research-{ev.session.id[:8]}.md",
                mime="text/markdown",
            )
            return

        elif isinstance(ev, Exception):
            if current_status is not None:
                current_status.update(state="error")
            st.error(f"Run failed: {ev}")
            return


# --- Entry point ------------------------------------------------------------


def main() -> None:
    _render_sidebar()

    viewing = st.session_state.get("viewing_session_id")
    if viewing:
        _render_history_view(viewing)
    else:
        _render_chat_view()


if __name__ == "__main__":
    main()
