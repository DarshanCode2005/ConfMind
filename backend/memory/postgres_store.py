"""
postgres_store.py — Async Supabase / PostgreSQL data store.

Provides three async functions used by agents and the API to persist
structured event data in PostgreSQL (hosted on Supabase free tier).

Configuration
─────────────
Set DATABASE_URL in .env:
    DATABASE_URL=postgresql+asyncpg://user:password@host:5432/confmind

Or individual Supabase vars (fill these in from your Supabase project dashboard):
    SUPABASE_URL=https://<project>.supabase.co
    SUPABASE_SERVICE_KEY=<service role key>

Schema
──────
See dataset/supabase_schema.sql for the full CREATE TABLE statements.

Tables used
────────────
events          — one row per EventSchema (from ETL pipeline / scraping)
plans           — one row per completed AgentState (full conference plan)

Public interface
────────────────
save_event(event)           -> str         INSERT + returns row UUID
get_events(filters)         -> list[...]   SELECT with optional WHERE
save_plan(state)            -> str         INSERT full plan as JSONB
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from dotenv import load_dotenv

from backend.models.schemas import AgentState, EventSchema

load_dotenv()

_DATABASE_URL = os.getenv("DATABASE_URL", "")


def _get_connection_pool() -> Any:
    """Return a shared asyncpg connection pool (lazy init).

    Used internally by all public functions.  Raises OSError if
    DATABASE_URL is not set.
    """
    if not _DATABASE_URL:
        raise OSError(
            "DATABASE_URL is not set.  Add it to your .env file.\n"
            "Example: DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/confmind"
        )
    # Pool is initialised lazily on first use — no cost at import time
    import asyncpg  # type: ignore[import-untyped]

    return asyncpg.create_pool(_DATABASE_URL)


async def save_event(event: EventSchema) -> str:
    """Persist a single EventSchema into the 'events' table.

    Upserts on (event_name, city) — re-running the scraper won't create
    duplicate rows for the same event.

    Args:
        event: A validated EventSchema object from the ETL pipeline.

    Returns:
        The UUID of the inserted/updated row as a string.

    Raises:
        OSError:  If DATABASE_URL is not configured.
        Exception: If the INSERT fails (network, constraint, etc.).

    Usage::

        event_id = await save_event(my_event_schema)
        print(f"Saved event with id {event_id}")
    """
    pool = await _get_connection_pool()
    row_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (
                id, event_name, date, city, country, category, theme,
                sponsors, speakers, exhibitors,
                ticket_price_early, ticket_price_general, ticket_price_vip,
                estimated_attendance, venue_name, venue_capacity, source_url
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
            ON CONFLICT (event_name, city) DO UPDATE SET
                date = EXCLUDED.date,
                category = EXCLUDED.category,
                estimated_attendance = EXCLUDED.estimated_attendance,
                source_url = EXCLUDED.source_url
            """,
            row_id,
            event.event_name,
            event.date,
            event.city,
            event.country,
            event.category,
            event.theme,
            json.dumps(event.sponsors),
            json.dumps(event.speakers),
            json.dumps(event.exhibitors),
            event.ticket_price_early,
            event.ticket_price_general,
            event.ticket_price_vip,
            event.estimated_attendance,
            event.venue_name,
            event.venue_capacity,
            event.source_url,
        )
    return row_id


async def get_events(filters: dict[str, Any] | None = None) -> list[EventSchema]:
    """Fetch events from the database with optional filtering.

    Args:
        filters: Optional dict of column→value filters applied as AND conditions.
                 Supported keys: category, city, country, date (exact match).
                 Pass None or {} to return all events (up to 500 rows).

    Returns:
        List of EventSchema objects; empty list if no rows match.

    Usage::

        ai_events = await get_events({"category": "AI", "country": "IN"})
    """
    pool = await _get_connection_pool()
    filters = filters or {}
    where_clauses: list[str] = []
    values: list[Any] = []
    for i, (col, val) in enumerate(filters.items(), start=1):
        where_clauses.append(f"{col} = ${i}")
        values.append(val)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql = f"SELECT * FROM events {where_sql} LIMIT 500"

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *values)

    return [
        EventSchema(
            event_name=r["event_name"],
            date=r["date"] or "",
            city=r["city"] or "",
            country=r["country"] or "",
            category=r["category"] or "",
            theme=r["theme"] or "",
            sponsors=json.loads(r["sponsors"] or "[]"),
            speakers=json.loads(r["speakers"] or "[]"),
            exhibitors=json.loads(r["exhibitors"] or "[]"),
            ticket_price_early=float(r["ticket_price_early"] or 0),
            ticket_price_general=float(r["ticket_price_general"] or 0),
            ticket_price_vip=float(r["ticket_price_vip"] or 0),
            estimated_attendance=int(r["estimated_attendance"] or 0),
            venue_name=r["venue_name"] or "",
            venue_capacity=r["venue_capacity"],
            source_url=r["source_url"] or "",
        )
        for r in rows
    ]


async def save_plan(state: AgentState) -> str:
    """Persist a completed AgentState (full conference plan) to the 'plans' table.

    Stores the entire state as JSONB — the frontend can retrieve it later by ID
    to re-render a previously generated conference plan.

    Args:
        state: The final AgentState after all 8 agents have run.

    Returns:
        The UUID of the saved plan row as a string.

    Usage::

        plan_id = await save_plan(final_state)
        # Return plan_id to the frontend so it can link to /plans/{plan_id}
    """
    pool = await _get_connection_pool()
    plan_id = str(uuid.uuid4())

    # Serialise state — EventConfigInput is a Pydantic model, needs .model_dump()
    cfg = state["event_config"]
    payload = {
        "event_config": cfg.model_dump(),
        "sponsors": [s.model_dump() for s in state.get("sponsors", [])],
        "speakers": [s.model_dump() for s in state.get("speakers", [])],
        "venues": [v.model_dump() for v in state.get("venues", [])],
        "exhibitors": [e.model_dump() for e in state.get("exhibitors", [])],
        "pricing": [t.model_dump() for t in state.get("pricing", [])],
        "communities": [c.model_dump() for c in state.get("communities", [])],
        "schedule": state.get("schedule", []),
        "revenue": state.get("revenue", {}),
        "gtm_messages": state.get("gtm_messages", {}),
        "errors": state.get("errors", []),
        "metadata": state.get("metadata", {}),
    }

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO plans (id, payload) VALUES ($1, $2)",
            plan_id,
            json.dumps(payload),
        )
    return plan_id
