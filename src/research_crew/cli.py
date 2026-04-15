"""Command-line interface for the Research Crew.

Usage:
    python -m research_crew "Your research question here"
    research-crew run "Your research question here"
    research-crew history --limit 10
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from research_crew.integrations import get_store
from research_crew.logging_conf import configure_logging
from research_crew.runner import ProgressEvent, run_research
from research_crew.settings import settings

app = typer.Typer(
    help="Multi-agent research crew powered by CrewAI + Supabase.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


@app.command(name="run")
def run_cmd(
    query: str = typer.Argument(..., help="The research question."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write the final brief to this markdown file."
    ),
) -> None:
    """Kick off a full research run and print the brief."""
    configure_logging()
    console.rule(f"[bold magenta]Research Crew[/] · model={settings.model_name}")
    console.print(Panel(query, title="Query", border_style="magenta"))

    def _on_progress(ev: ProgressEvent) -> None:
        console.rule(f"[bold cyan]{ev.agent_role}[/] · {ev.task_name}")
        console.print(Markdown(ev.output))

    result = run_research(query, on_progress=_on_progress)

    console.rule("[bold green]Final brief")
    console.print(Markdown(result.report_markdown))
    console.print(
        f"\n[dim]Session {result.session.id} · {result.duration_seconds:.1f}s[/]"
    )

    if output is not None:
        output.write_text(result.report_markdown, encoding="utf-8")
        console.print(f"[green]✓[/] Wrote {output}")


@app.command(name="history")
def history_cmd(
    limit: int = typer.Option(10, "--limit", "-n", help="Max sessions to show."),
) -> None:
    """List recent research sessions from Supabase."""
    configure_logging()
    sessions = get_store().list_recent_sessions(limit=limit)

    table = Table(title="Recent research sessions", show_lines=False)
    table.add_column("id", style="dim", no_wrap=True)
    table.add_column("created", no_wrap=True)
    table.add_column("status")
    table.add_column("model", no_wrap=True)
    table.add_column("query")

    for s in sessions:
        status_style = {
            "completed": "green",
            "running": "yellow",
            "failed": "red",
        }.get(s.status, "white")
        preview = (s.query[:70] + "…") if len(s.query) > 70 else s.query
        table.add_row(
            s.id[:8],
            s.created_at[:19].replace("T", " "),
            f"[{status_style}]{s.status}[/]",
            s.model,
            preview,
        )

    console.print(table)


@app.command(name="show")
def show_cmd(session_id: str = typer.Argument(..., help="Session UUID or prefix.")) -> None:
    """Print the final brief for a past session."""
    configure_logging()
    store = get_store()
    session = store.get_session(session_id)
    if session is None:
        # Fallback: try prefix match against recent sessions
        for s in store.list_recent_sessions(limit=200):
            if s.id.startswith(session_id):
                session = s
                break

    if session is None:
        console.print(f"[red]No session matching {session_id}[/]")
        raise typer.Exit(code=1)

    console.rule(f"[bold magenta]{session.query}")
    console.print(
        f"[dim]id={session.id} · status={session.status} · "
        f"model={session.model} · duration={session.duration_seconds or 0:.1f}s[/]\n"
    )
    if session.report_markdown:
        console.print(Markdown(session.report_markdown))
    else:
        console.print("[yellow]No report available for this session.[/]")


if __name__ == "__main__":
    app()
