# Research Crew — a CrewAI Multi-Agent Demo

A production-grade reference implementation of a **multi-agent research assistant** built on
[CrewAI](https://github.com/crewAIInc/crewAI), persisted to [Supabase](https://supabase.com),
and wrapped in a streaming [Streamlit](https://streamlit.io) UI — all deployable to
[Railway](https://railway.app) with a single command.

Give it a question. Four specialised agents — **Planner → Researcher → Analyst → Writer** —
collaborate to produce an executive-ready brief with cited sources, while the full trace
(per-agent output, timing, final report) is persisted to Supabase for later review.

---

## Why this demo

This repo is intentionally scoped to show, in a single afternoon of reading, that whoever
wrote it can:

- design and wire a **multi-agent architecture** (planner + execution + tool-use)
- orchestrate LLMs with **CrewAI** using production patterns (YAML config, typed settings,
  task callbacks, per-task persistence)
- integrate **tool-calling** (web search) with a sensible zero-config default and a paid upgrade path
- persist and retrieve sessions via a real database integration (**Supabase**)
- ship a **real UI** with streaming agent output, session history, and brief downloads
- build for **deployability** (Railway, Docker, Nixpacks, healthchecks, non-root user)

---

## Architecture

```
           ┌────────────────────────── Streamlit UI ──────────────────────────┐
           │  chat input  ·  live agent trace  ·  session history sidebar      │
           └───────────────┬────────────────────────────┬──────────────────────┘
                           │                            │
                           ▼                            ▼
                 ┌─────────────────┐          ┌──────────────────────┐
                 │  runner.py      │          │  ResearchStore       │
                 │  (orchestrates) │◄────────►│  (Supabase facade)   │
                 └────────┬────────┘          └──────────┬───────────┘
                          │                              │
                          ▼                              ▼
                 ┌─────────────────┐          ┌──────────────────────┐
                 │  CrewAI Crew    │          │  Supabase Postgres   │
                 │  (4 agents)     │          │  sessions/artifacts  │
                 └────────┬────────┘          └──────────────────────┘
                          │
         ┌────────────────┼────────────────┬────────────────┐
         ▼                ▼                ▼                ▼
    ┌─────────┐     ┌──────────┐     ┌──────────┐     ┌─────────┐
    │ Planner │ ──► │Researcher│ ──► │ Analyst  │ ──► │ Writer  │
    └─────────┘     └────┬─────┘     └──────────┘     └─────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │ web_search  │   DuckDuckGo (default) / Serper (optional)
                  └─────────────┘
```

### Project layout

```
crewai-research-agent-demo/
├── streamlit_app.py                 # Streamlit entry point (Railway web service)
├── src/research_crew/
│   ├── cli.py                       # Typer CLI (`python -m research_crew …`)
│   ├── crew.py                      # CrewBase class: agents, tasks, crew()
│   ├── runner.py                    # Orchestrates crew + Supabase persistence
│   ├── settings.py                  # Typed config (pydantic-settings)
│   ├── logging_conf.py              # Rich-based structured logging
│   ├── config/
│   │   ├── agents.yaml              # Agent roles, goals, backstories
│   │   └── tasks.yaml               # Task prompts + contexts
│   ├── tools/
│   │   └── web_search.py            # DuckDuckGo tool + Serper upgrade
│   └── integrations/
│       └── supabase_client.py       # ResearchStore facade
├── supabase/migrations/
│   └── 0001_init.sql                # Schema: research_sessions, research_artifacts
├── tests/                           # pytest suite (no network)
├── pyproject.toml                   # Canonical project metadata
├── requirements.txt                 # Pinned deps for Railway / Docker
├── Procfile                         # Railway start command
├── railway.json                     # Railway build + healthcheck config
├── nixpacks.toml                    # Nixpacks build (Railway default)
├── Dockerfile                       # Alternative deploy target
├── Makefile                         # DX helpers (install / run / test / lint)
└── .env.example                     # Required environment variables
```

---

## Quick start (local)

### 1. Prerequisites

- Python 3.11+
- A Supabase project (free tier is fine)
- An OpenAI API key (or any LiteLLM-supported provider — see `MODEL_NAME` below)

### 2. Install

```bash
git clone <this-repo> crewai-research-agent-demo
cd crewai-research-agent-demo

make install           # creates .venv and installs the package in editable mode
# or, without make:
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configure

```bash
cp .env.example .env
# fill in: SUPABASE_*, OPENAI_API_KEY (or ANTHROPIC_API_KEY)
```

### 4. Apply the Supabase schema

Open your Supabase project → **SQL Editor**, paste the contents of
`supabase/migrations/0001_init.sql`, and run it. Two tables appear under
`public`: `research_sessions` and `research_artifacts`.

### 5. Run the UI

```bash
make run
# or: streamlit run streamlit_app.py
```

Open <http://localhost:8501> and ask the crew a research question.

### 6. Or use the CLI

```bash
python -m research_crew run "Competitive landscape for AI agent platforms in 2026"
python -m research_crew history --limit 10
python -m research_crew show <session-id-prefix>
```

---

## Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ | — | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ | — | Anon key (present for symmetry with frontend) |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | — | Service-role key used server-side by the Python app |
| `OPENAI_API_KEY` | ✳️ | — | Required when `MODEL_NAME` starts with `openai/` |
| `ANTHROPIC_API_KEY` | ✳️ | — | Required when `MODEL_NAME` starts with `anthropic/` |
| `MODEL_NAME` | — | `openai/gpt-4o-mini` | Any LiteLLM-supported model slug |
| `SERPER_API_KEY` | — | *(unset)* | Enables premium web search; falls back to DuckDuckGo when unset |
| `LOG_LEVEL` | — | `INFO` | Python logging level |
| `HISTORY_LIMIT` | — | `25` | Max sessions shown in the UI sidebar |

> 🔒 The **service-role key** bypasses Supabase Row Level Security. It must never be
> exposed to the browser — this repo keeps it on the Python server only. Anon key is
> kept in the env for parity with any frontend consumers.

---

## Deploying to Railway

Two paths — pick whichever you prefer.

### Option A — Nixpacks (default, zero-config)

1. Push this repo to GitHub.
2. In Railway, **New Project → Deploy from GitHub** and pick this repo.
3. Under **Variables**, paste every entry from `.env.example` with real values.
4. Railway detects `railway.json` + `nixpacks.toml`, builds with Python 3.11, and starts
   Streamlit on `$PORT`. The healthcheck hits `/_stcore/health`.
5. Click the generated public URL — done.

### Option B — Dockerfile

If you prefer Docker:

1. In Railway, **Settings → Build → Builder = Dockerfile**.
2. Redeploy. The included `Dockerfile` uses a non-root user, pins Python 3.11, and
   exposes a healthcheck.

### CLI deploy

```bash
railway login
railway init
railway up
railway variables set \
  NEXT_PUBLIC_SUPABASE_URL=... \
  NEXT_PUBLIC_SUPABASE_ANON_KEY=... \
  SUPABASE_SERVICE_ROLE_KEY=... \
  OPENAI_API_KEY=... \
  MODEL_NAME=openai/gpt-4o-mini
railway domain   # mint a public URL
```

---

## Deploying to Streamlit Community Cloud

Yes — this repo deploys to [Streamlit Community Cloud](https://share.streamlit.io)
with no code changes.

1. Push the repo to GitHub.
2. [share.streamlit.io](https://share.streamlit.io) → **New app** → pick your repo.
   - **Main file path:** `streamlit_app.py`
   - **Python version:** `3.11`
3. Under **⋯ → Settings → Secrets**, paste the contents of
   `.streamlit/secrets.toml.example` with real values. Save.
4. The app restarts and is live at `https://<your-slug>.streamlit.app`.

### How secrets work here

`streamlit_app.py` calls `_bootstrap_secrets()` before any `research_crew` import.
That helper copies every scalar key from `st.secrets` into `os.environ`, so
`pydantic-settings` picks them up exactly as it does from a local `.env` file.
The same code therefore runs unchanged on local / Railway / SCC.

### Community Cloud caveats

- **Memory:** free tier caps at ~1 GB RAM. CrewAI's install is heavy but fits;
  if you hit OOM during a run, switch `MODEL_NAME` to a lighter model and keep
  the DuckDuckGo tool (no Serper) to trim memory.
- **Build time:** first boot pulls a lot of deps (~3–5 min). Subsequent boots
  are cached.
- **Cold starts / sleep:** free apps sleep after inactivity. First request after
  a sleep takes ~30 s to wake.
- **Secrets visibility:** SCC stores secrets encrypted but a compromised repo
  collaborator can read them. Treat the dashboard like prod IAM.

The `Procfile`, `railway.json`, `nixpacks.toml`, and `Dockerfile` are all
ignored by SCC — safe to leave in place for multi-target deploys.

---

## Swapping the LLM

`MODEL_NAME` is passed straight to LiteLLM, so anything on
[LiteLLM's provider list](https://docs.litellm.ai/docs/providers) works.

```env
# OpenAI (default)
MODEL_NAME=openai/gpt-4o-mini

# Anthropic
MODEL_NAME=anthropic/claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...

# Groq
MODEL_NAME=groq/llama-3.3-70b-versatile
GROQ_API_KEY=...
```

No code changes required.

---

## Upgrading web search

The default `DuckDuckGoSearchTool` works out of the box, no key needed. For more
consistent coverage, drop a free [Serper](https://serper.dev) key into `SERPER_API_KEY`;
the crew automatically switches to `SerperDevTool`.

---

## Testing

```bash
make test           # pytest, no network calls
make lint           # ruff
make typecheck      # mypy
```

The test suite mocks Supabase via an in-memory fake client, so it runs hermetically and
fast (≈1 s on a laptop).

---

## Production notes

- **Secrets:** only the Python server touches `SUPABASE_SERVICE_ROLE_KEY`. The Streamlit
  process runs as a non-root user in Docker.
- **Row Level Security** is enabled on both tables and no anon policies are created — so
  leaking the anon key is inert.
- **Retries:** DuckDuckGo calls are wrapped in `tenacity` with exponential backoff.
- **Failure isolation:** Supabase write failures never break the crew run — they log and
  continue. Crew failures are persisted as `status='failed'` with the truncated error.
- **Observability:** every run gets a UUID, duration, per-task artifact trail, and a
  structured log line.

---

## Extending the crew

Want to add an agent? Three small edits:

1. Add a role block to `src/research_crew/config/agents.yaml`.
2. Add a task block to `src/research_crew/config/tasks.yaml` (set `context:` to any upstream tasks).
3. Add one `@agent` method and one `@task` method in `src/research_crew/crew.py`.

That's it — the sequential process will pick it up, and the runner will persist its
output as another artifact automatically.

---

## Roadmap ideas

- Long-term memory across sessions (pgvector + CrewAI `Memory`)
- Scheduled re-runs (Railway cron → `python -m research_crew run …`)
- Streaming token output in Streamlit (per-agent token stream)
- Slack / Discord integration: new brief → post to channel

---

## License

MIT. Use it, fork it, rip it apart in an interview.
