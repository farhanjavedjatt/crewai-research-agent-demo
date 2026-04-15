"""ResearchStore should round-trip data through the Supabase table API."""

from __future__ import annotations

from typing import Any

import pytest

from research_crew.integrations.supabase_client import ResearchStore, SessionRecord


class _FakeQuery:
    """In-memory stand-in for the Supabase query builder."""

    def __init__(self, table: "_FakeTable", action: str) -> None:
        self.table = table
        self.action = action
        self._payload: Any = None
        self._filter: tuple[str, Any] | None = None
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None
        self._update_payload: dict[str, Any] | None = None

    # Mutators --------------------------------------------------------------
    def insert(self, payload: Any) -> "_FakeQuery":
        self._payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> "_FakeQuery":
        self._update_payload = payload
        return self

    def select(self, _columns: str = "*") -> "_FakeQuery":
        return self

    def eq(self, column: str, value: Any) -> "_FakeQuery":
        self._filter = (column, value)
        return self

    def order(self, column: str, desc: bool = False) -> "_FakeQuery":
        self._order = (column, desc)
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._limit = n
        return self

    # Terminal --------------------------------------------------------------
    def execute(self) -> Any:
        if self.action == "insert" and isinstance(self._payload, dict):
            self.table.rows.append(dict(self._payload))
            return _Response(data=[self._payload])

        if self.action == "update" and self._update_payload and self._filter:
            col, value = self._filter
            for row in self.table.rows:
                if row.get(col) == value:
                    row.update(self._update_payload)
            return _Response(data=self.table.rows)

        if self.action == "select":
            rows = list(self.table.rows)
            if self._filter:
                col, value = self._filter
                rows = [r for r in rows if r.get(col) == value]
            if self._order:
                col, desc = self._order
                rows.sort(key=lambda r: r.get(col, ""), reverse=desc)
            if self._limit is not None:
                rows = rows[: self._limit]
            return _Response(data=rows)

        return _Response(data=[])


class _Response:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _FakeTable:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def insert(self, payload: Any) -> _FakeQuery:
        return _FakeQuery(self, "insert").insert(payload)

    def update(self, payload: dict[str, Any]) -> _FakeQuery:
        return _FakeQuery(self, "update").update(payload)

    def select(self, columns: str = "*") -> _FakeQuery:
        return _FakeQuery(self, "select").select(columns)


class _FakeClient:
    def __init__(self) -> None:
        self._tables: dict[str, _FakeTable] = {}

    def table(self, name: str) -> _FakeTable:
        return self._tables.setdefault(name, _FakeTable())


@pytest.fixture
def store() -> ResearchStore:
    return ResearchStore(_FakeClient())  # type: ignore[arg-type]


def test_session_lifecycle(store: ResearchStore) -> None:
    session = store.create_session(query="Hello world", model="openai/gpt-4o-mini")
    assert session.status == "running"
    assert session.query == "Hello world"

    store.record_artifact(
        session.id,
        agent_role="Planner",
        task_name="plan_task",
        content="1. Do the thing",
        sequence=1,
    )
    artifacts = store.list_artifacts(session.id)
    assert len(artifacts) == 1
    assert artifacts[0]["content"] == "1. Do the thing"

    store.complete_session(
        session.id,
        report_markdown="# brief",
        duration_seconds=12.3,
    )
    fetched = store.get_session(session.id)
    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.duration_seconds == pytest.approx(12.3)
    assert fetched.report_markdown == "# brief"


def test_list_recent_sessions_orders_desc(store: ResearchStore) -> None:
    for i in range(3):
        store.create_session(query=f"q{i}", model="openai/gpt-4o-mini")

    sessions = store.list_recent_sessions(limit=2)
    assert len(sessions) == 2
    # _utc_now_iso is strictly increasing within a process so newest is first.
    assert sessions[0].created_at >= sessions[1].created_at


def test_fail_session_marks_error(store: ResearchStore) -> None:
    session = store.create_session(query="q", model="openai/gpt-4o-mini")
    store.fail_session(session.id, "boom")
    fetched = store.get_session(session.id)
    assert fetched is not None
    assert fetched.status == "failed"
    assert fetched.metadata.get("error") == "boom"


def test_session_record_from_row_defaults() -> None:
    record = SessionRecord.from_row(
        {
            "id": "abc",
            "query": "q",
            "status": "running",
            "model": "",
            "created_at": "2026-04-16T00:00:00Z",
        }
    )
    assert record.report_markdown is None
    assert record.metadata == {}
