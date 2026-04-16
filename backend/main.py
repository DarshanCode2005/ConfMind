"""
main.py — FastAPI application entry point for ConfMind.

Three REST routes:
    POST /api/run-plan       Accept EventConfigInput → invoke LangGraph → return plan
    GET  /api/agent-status   Server-Sent Events stream of agent completion progress
    GET  /api/output/{id}    Retrieve a previously saved plan by UUID

Running locally (inside venv)
──────────────────────────────
    uvicorn backend.main:api --reload --port 8000

Then open http://localhost:8000/docs for the interactive Swagger UI.

Environment variables (all from .env)
──────────────────────────────────────
    OPENAI_API_KEY   Required — used by agents
    DATABASE_URL     Optional — Supabase/PostgreSQL for plan persistence
    ALLOWED_ORIGINS  Comma-separated CORS origins (default: http://localhost:3000)
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib import import_module
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.models.schemas import AgentState, EventConfigInput

load_dotenv()

# ── In-memory plan cache ─────────────────────────────────────────────────────
# Stores final AgentState dicts keyed by plan_id (UUID string).
# Replaced by Postgres in production — see backend/memory/postgres_store.py.
_plan_cache: dict[str, Any] = {}
_agent_status: dict[str, dict[str, str]] = {}  # plan_id -> {agent_name -> status}
_latest_plan_id: str | None = None


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan: runs on startup and teardown."""
    # Validate required environment variables on startup
    if not os.getenv("OPENAI_API_KEY"):
        import warnings

        warnings.warn(
            "OPENAI_API_KEY is not set — agents will fail when called. Add it to your .env file.",
            stacklevel=1,
        )

    if not os.getenv("LANGCHAIN_API_KEY"):
        import warnings

        warnings.warn(
            "LANGCHAIN_API_KEY is not set — monitoring via LangSmith is disabled.",
            stacklevel=1,
        )
    yield
    # Teardown: nothing to clean up in dev mode


# ── FastAPI app ───────────────────────────────────────────────────────────────

api = FastAPI(
    title="ConfMind API",
    description="Multi-agent conference planning system — LangGraph orchestrator REST interface.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js dev server and any configured origins
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
_origins = [o.strip() for o in _raw_origins.split(",")]

api.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ────────────────────────────────────────────────────────────────────


@api.post(
    "/api/run-plan",
    summary="Run the full conference planning pipeline",
    response_description="The complete AgentState after all 8 agents have run.",
)
async def run_plan_endpoint(config: EventConfigInput) -> dict[str, Any]:
    """Accept an EventConfigInput and invoke the LangGraph orchestrator.

    The orchestrator runs up to 8 specialized agents in sequence/parallel and
    returns the complete conference plan as structured JSON.

    **Body** (all fields required unless noted):
    - `category` — Event type: "AI", "Web3", "ClimateTech", "Music", "Sports"
    - `geography` — Target region: "Europe", "India", "USA", "Singapore"
    - `audience_size` — Expected attendees (integer ≥ 1)
    - `budget_usd` — Total budget in USD (float ≥ 0)
    - `event_dates` — ISO 8601 date string e.g. "2025-09-15"
    - `event_name` — Optional custom name; defaults to "{category} Summit"
    """
    import uuid

    orchestrator = import_module("backend.orchestrator")

    global _latest_plan_id
    plan_id = str(uuid.uuid4())
    _agent_status[plan_id] = {}
    _latest_plan_id = plan_id

    try:
        run_plan_fn = orchestrator.run_plan
        final_state: AgentState = await run_plan_fn(config, plan_id=plan_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Serialise for JSON response (Pydantic models need .model_dump())
    cfg_dict = config.model_dump()
    response: dict[str, Any] = {
        "plan_id": plan_id,
        "event_config": cfg_dict,
        "sponsors": [s.model_dump() for s in final_state.get("sponsors", [])],
        "speakers": [s.model_dump() for s in final_state.get("speakers", [])],
        "venues": [v.model_dump() for v in final_state.get("venues", [])],
        "exhibitors": [e.model_dump() for e in final_state.get("exhibitors", [])],
        "pricing": [t.model_dump() for t in final_state.get("pricing", [])],
        "communities": [c.model_dump() for c in final_state.get("communities", [])],
        "schedule": final_state.get("schedule", []),
        "revenue": final_state.get("revenue", {}),
        "gtm_messages": final_state.get("gtm_messages", {}),
        "errors": final_state.get("errors", []),
        "metadata": final_state.get("metadata", {}),
    }

    # Cache plan for /api/output/{id}
    _plan_cache[plan_id] = response

    # Optionally persist to Postgres (non-blocking, ignore result)
    _bg_task = asyncio.create_task(_persist_plan_silently(final_state))
    _bg_task.add_done_callback(lambda _: None)  # suppress RUF006 "unhandled task"

    return response


@api.get(
    "/api/agent-status",
    summary="Stream agent execution status via Server-Sent Events",
    response_class=StreamingResponse,
)
async def agent_status_stream(plan_id: str | None = None) -> StreamingResponse:
    """SSE endpoint — the frontend polls this while /api/run-plan is executing.

    Each event is a JSON object: `{ "agent": "sponsor_agent", "status": "done" }`

    Query params:
    - `plan_id` — the UUID returned by /api/run-plan
    """

    resolved_plan_id = plan_id or _latest_plan_id
    if not resolved_plan_id:
        raise HTTPException(
            status_code=400,
            detail="plan_id is required. Call /api/run-plan first and use the returned plan_id.",
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        last_count = 0
        while True:
            status = _agent_status.get(resolved_plan_id, {})
            items = list(status.items())
            for agent_name, agent_status_val in items[last_count:]:
                data = json.dumps({"agent": agent_name, "status": agent_status_val})
                yield f"data: {data}\n\n"
            last_count = len(items)
            if len(status) >= 8:  # all 8 agents reported
                yield 'data: {"agent": "__all__", "status": "done"}\n\n'
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@api.get(
    "/api/output",
    summary="Retrieve the most recently generated conference plan",
)
async def get_latest_output() -> dict[str, Any]:
    """Return the latest cached plan when the caller does not provide an ID."""
    if _latest_plan_id and _latest_plan_id in _plan_cache:
        return _plan_cache[_latest_plan_id]
    raise HTTPException(status_code=404, detail="No completed plan is available yet.")


@api.get(
    "/api/output/{plan_id}",
    summary="Retrieve a previously generated conference plan",
)
async def get_output(plan_id: str) -> dict[str, Any]:
    """Return the full JSON output for a completed plan by its UUID.

    The plan is read from the in-memory cache (dev) or Postgres (prod).

    Returns 404 if the plan_id is not found.
    """
    if plan_id in _plan_cache:
        return _plan_cache[plan_id]
    # Try Postgres as fallback
    try:
        from backend.memory.postgres_store import get_events as _  # noqa: F401
        # TODO: implement get_plan(plan_id) in postgres_store when Supabase is ready
    except Exception:
        pass
    raise HTTPException(status_code=404, detail=f"Plan {plan_id!r} not found.")


@api.get("/health", summary="Health check")
async def health() -> dict[str, str]:
    """Simple liveness probe used by Railway/Render deployment checks."""
    return {"status": "ok", "service": "confmind-api"}


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _persist_plan_silently(state: AgentState) -> None:
    """Fire-and-forget Postgres persistence — errors are logged but not raised."""
    try:
        from backend.memory.postgres_store import save_plan

        await save_plan(state)
    except Exception:
        pass  # Postgres not configured yet in dev — that's fine
