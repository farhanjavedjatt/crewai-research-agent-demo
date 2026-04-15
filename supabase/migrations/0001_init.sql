-- Research Crew — initial schema
-- Run this once in the Supabase SQL editor (or via `supabase db push`).
-- Safe to re-run.

create extension if not exists "pgcrypto";

-- Every crew invocation is one session.
create table if not exists public.research_sessions (
    id                uuid primary key default gen_random_uuid(),
    query             text not null,
    status            text not null check (status in ('running', 'completed', 'failed')),
    model             text not null default '',
    created_at        timestamptz not null default now(),
    completed_at      timestamptz,
    duration_seconds  double precision,
    report_markdown   text,
    metadata          jsonb not null default '{}'::jsonb
);

create index if not exists research_sessions_created_at_idx
    on public.research_sessions (created_at desc);

create index if not exists research_sessions_status_idx
    on public.research_sessions (status);

-- Per-agent output captured during a session (plan / research / analysis / writeup).
create table if not exists public.research_artifacts (
    id           uuid primary key default gen_random_uuid(),
    session_id   uuid not null references public.research_sessions(id) on delete cascade,
    agent_role   text not null,
    task_name    text not null,
    sequence     integer not null,
    content      text not null,
    created_at   timestamptz not null default now()
);

create index if not exists research_artifacts_session_idx
    on public.research_artifacts (session_id, sequence);

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
-- The service role (used server-side by the Streamlit backend) bypasses RLS.
-- We still enable RLS and leave anon/authenticated without policies so that
-- exposed anon keys can never read or write these tables directly.

alter table public.research_sessions  enable row level security;
alter table public.research_artifacts enable row level security;

-- No policies are created intentionally. Access is server-only via service role.

comment on table public.research_sessions  is 'One row per crew run (Research Crew demo).';
comment on table public.research_artifacts is 'Per-agent / per-task output captured during a session.';
