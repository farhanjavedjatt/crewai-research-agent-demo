"""Supabase persistence layer.

This module is the *only* place in the codebase that talks to Supabase.
Everything else consumes the typed :class:`ResearchStore` interface below,
which keeps schema knowledge localised and trivially mockable in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

from supabase import Client, create_client

from research_crew.logging_conf import get_logger
from research_crew.settings import settings

logger = get_logger(__name__)

SESSIONS_TABLE = "research_sessions"
ARTIFACTS_TABLE = "research_artifacts"


@dataclass(slots=True)
class SessionRecord:
    """A single research run persisted to Supabase."""

    id: str
    query: str
    status: str
    model: str
    created_at: str
    completed_at: str | None = None
    report_markdown: str | None = None
    duration_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> SessionRecord:
        return cls(
            id=row["id"],
            query=row["query"],
            status=row["status"],
            model=row.get("model", ""),
            created_at=row["created_at"],
            completed_at=row.get("completed_at"),
            report_markdown=row.get("report_markdown"),
            duration_seconds=row.get("duration_seconds"),
            metadata=row.get("metadata") or {},
        )


class ResearchStore:
    """Typed facade over the Supabase tables used by this project."""

    def __init__(self, client: Client) -> None:
        self._client = client

    # --- Session lifecycle -------------------------------------------------

    def create_session(self, query: str, model: str) -> SessionRecord:
        session_id = str(uuid4())
        payload = {
            "id": session_id,
            "query": query.strip(),
            "status": "running",
            "model": model,
            "created_at": _utc_now_iso(),
        }
        self._client.table(SESSIONS_TABLE).insert(payload).execute()
        logger.info("Created research session %s", session_id)
        return SessionRecord.from_row(payload)

    def complete_session(
        self,
        session_id: str,
        *,
        report_markdown: str,
        duration_seconds: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._client.table(SESSIONS_TABLE).update(
            {
                "status": "completed",
                "completed_at": _utc_now_iso(),
                "report_markdown": report_markdown,
                "duration_seconds": duration_seconds,
                "metadata": metadata or {},
            }
        ).eq("id", session_id).execute()
        logger.info("Completed research session %s in %.2fs", session_id, duration_seconds)

    def fail_session(self, session_id: str, error: str) -> None:
        self._client.table(SESSIONS_TABLE).update(
            {
                "status": "failed",
                "completed_at": _utc_now_iso(),
                "metadata": {"error": error[:2000]},
            }
        ).eq("id", session_id).execute()
        logger.error("Marked session %s as failed: %s", session_id, error)

    # --- Artifacts (per-agent outputs) -------------------------------------

    def record_artifact(
        self,
        session_id: str,
        *,
        agent_role: str,
        task_name: str,
        content: str,
        sequence: int,
    ) -> None:
        self._client.table(ARTIFACTS_TABLE).insert(
            {
                "id": str(uuid4()),
                "session_id": session_id,
                "agent_role": agent_role,
                "task_name": task_name,
                "content": content,
                "sequence": sequence,
                "created_at": _utc_now_iso(),
            }
        ).execute()

    # --- Reads -------------------------------------------------------------

    def list_recent_sessions(self, limit: int = 25) -> list[SessionRecord]:
        response = (
            self._client.table(SESSIONS_TABLE)
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [SessionRecord.from_row(row) for row in response.data or []]

    def get_session(self, session_id: str) -> SessionRecord | None:
        response = (
            self._client.table(SESSIONS_TABLE)
            .select("*")
            .eq("id", session_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return SessionRecord.from_row(rows[0]) if rows else None

    def list_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        response = (
            self._client.table(ARTIFACTS_TABLE)
            .select("*")
            .eq("session_id", session_id)
            .order("sequence")
            .execute()
        )
        return list(response.data or [])


# --- Module-level helpers ---------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@lru_cache(maxsize=1)
def _build_client() -> Client:
    """Build a Supabase client using the service-role key.

    Service role bypasses RLS, which is appropriate for server-side code. We
    never expose this key to the browser — the Streamlit server owns it.
    """
    url = settings.supabase_url
    key = settings.supabase_service_role_key.get_secret_value()
    return create_client(url, key)


@lru_cache(maxsize=1)
def get_store() -> ResearchStore:
    return ResearchStore(_build_client())
