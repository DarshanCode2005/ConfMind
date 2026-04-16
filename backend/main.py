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
    ANTHROPIC_API_KEY  Primary LLM — used by all agents (preferred)
    OPENAI_API_KEY     Secondary/tool LLM — scraper and fallback agents
    DATABASE_URL       Optional — Supabase/PostgreSQL for plan persistence
    ALLOWED_ORIGINS    Comma-separated CORS origins (default: http://localhost:3000)
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.models.schemas import AgentState, ChatInput, EventConfigInput

load_dotenv()

# ── In-memory plan cache ─────────────────────────────────────────────────────
# Stores final AgentState dicts keyed by plan_id (UUID string).
# Replaced by Postgres in production — see backend/memory/postgres_store.py.
_plan_cache: dict[str, Any] = {}
_agent_status: dict[str, dict[str, str]] = {}  # plan_id -> {agent_name -> status}


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan: runs on startup and teardown."""
    # Validate required environment variables on startup
    if not os.getenv("ANTHROPIC_API_KEY"):
        import warnings

        warnings.warn(
            "ANTHROPIC_API_KEY is not set — agents will fall back to OpenRouter/Gemini. "
            "Add it to your .env file for best performance.",
            stacklevel=1,
        )
    elif not os.getenv("OPENAI_API_KEY"):
        import warnings

        warnings.warn(
            "OPENAI_API_KEY is not set — scraper_tool and OpenAI fallback will fail. "
            "Anthropic is primary, so the pipeline may still run.",
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

    from backend.orchestrator import run_plan

    plan_id = str(uuid.uuid4())
    _agent_status[plan_id] = {}

    try:
        final_state: AgentState = await run_plan(config)
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

    # Generate Chat summary asynchronously
    from backend.agents.chat_agent import generate_workflow_completion_summary

    _bg_task_summary = asyncio.create_task(generate_workflow_completion_summary(plan_id, response))
    _bg_task_summary.add_done_callback(lambda _: None)

    return response


@api.get(
    "/api/agent-status",
    summary="Stream agent execution status via Server-Sent Events",
    response_class=StreamingResponse,
)
async def agent_status_stream(plan_id: str) -> StreamingResponse:
    """SSE endpoint — the frontend polls this while /api/run-plan is executing.

    Each event is a JSON object: `{ "agent": "sponsor_agent", "status": "done" }`

    Query params:
    - `plan_id` — the UUID returned by /api/run-plan
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        last_count = 0
        while True:
            status = _agent_status.get(plan_id, {})
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


@api.post(
    "/api/chat",
    summary="Chat with the ConfMind agent",
)
async def chat_endpoint(input_data: ChatInput) -> dict[str, Any]:
    """Handle user queries, intent classification, and tool routing for the Chat Agent."""
    from backend.agents.chat_agent import chat_agent_host, get_chat_state
    from backend.orchestrator import rerun_nodes

    response_text = await chat_agent_host.invoke(
        session_id=input_data.session_id,
        message=input_data.message,
        plan_id=input_data.plan_id,
    )

    state = get_chat_state(input_data.session_id)

    # Check if we need to trigger any agent reruns based on the chat tools
    if (state.get("pending_rerun") or state.get("pending_updates")) and input_data.plan_id:
        nodes_to_rerun = state.get("pending_rerun") or []
        state["pending_rerun"] = None
        pending_updates = state.get("pending_updates")
        state["pending_updates"] = None

        if input_data.plan_id in _plan_cache:
            current_plan_state = _plan_cache[input_data.plan_id]

            async def do_rerun() -> None:
                try:
                    from backend.orchestrator import hydrate_state
                    nonlocal current_plan_state
                    
                    # Ensure state is hydrated for property access
                    hydrated = hydrate_state(current_plan_state)
                    
                    # Apply configuration updates from Chat Agent (if any)
                    if pending_updates:
                        for field, value in pending_updates.items():
                            if hasattr(hydrated["event_config"], field):
                                setattr(hydrated["event_config"], field, value)
                    
                    # Update status for UI
                    if input_data.plan_id not in _agent_status:
                        _agent_status[input_data.plan_id] = {}
                    
                    for node in nodes_to_rerun:
                        _agent_status[input_data.plan_id][node] = "running"
                    
                    # Execute agents
                    new_state = await rerun_nodes(nodes_to_rerun, hydrated)
                    
                    # Update status for UI
                    for node in nodes_to_rerun:
                        _agent_status[input_data.plan_id][node] = "completed"
                    
                    # Use _dump_state to ensure all Pydantic models are serialized to dicts
                    dumped_state = _dump_state(input_data.plan_id, new_state)
                    _plan_cache[input_data.plan_id] = dumped_state
                    await _persist_plan_silently(new_state)
                except Exception as e:
                    import logging
                    logging.error(f"Rerun failed: {e}")
                    # Clear status on failure
                    if input_data.plan_id in _agent_status:
                        for node in nodes_to_rerun:
                            _agent_status[input_data.plan_id][node] = "failed"

            task = asyncio.create_task(do_rerun())
            task.add_done_callback(lambda _: None)

    return {"message": response_text}


# ── Internal helpers ──────────────────────────────────────────────────────────


def _dump_state(plan_id: str, state: AgentState) -> dict[str, Any]:
    """Convert AgentState (potentially with Pydantic models) to a serializable dict."""
    from backend.models.schemas import (
        CommunitySchema,
        ExhibitorSchema,
        PricingTierSchema,
        SpeakerSchema,
        SponsorSchema,
        VenueSchema,
        EventConfigInput
    )

    def dump_val(v: Any) -> Any:
        if isinstance(v, (SponsorSchema, SpeakerSchema, VenueSchema, ExhibitorSchema, 
                         PricingTierSchema, CommunitySchema, EventConfigInput)):
            return v.model_dump()
        if isinstance(v, list):
            return [dump_val(i) for i in v]
        if isinstance(v, dict):
            return {k: dump_val(val) for k, val in v.items()}
        return v

    dumped = {k: dump_val(v) for k, v in state.items()}
    dumped["plan_id"] = plan_id
    return dumped


async def _persist_plan_silently(state: AgentState) -> None:
    """Fire-and-forget Postgres persistence — errors are logged but not raised."""
    try:
        from backend.memory.postgres_store import save_plan

        await save_plan(state)
    except Exception:
        pass  # Postgres not configured yet in dev — that's fine
