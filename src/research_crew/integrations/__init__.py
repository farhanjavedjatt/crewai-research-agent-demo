"""Third-party integrations. Currently: Supabase."""

from research_crew.integrations.supabase_client import (
    ResearchStore,
    SessionRecord,
    get_store,
)

__all__ = ["ResearchStore", "SessionRecord", "get_store"]
