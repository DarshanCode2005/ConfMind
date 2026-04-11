# Backend — Internal Architecture Documentation

Complete reference for every module in `backend/`.  Written for both your teammates and for AI agents that will help wire it together.

---

## Module Map

```
backend/
├── main.py              FastAPI entry point — REST API gateway
├── orchestrator.py      LangGraph StateGraph — 8 agent nodes + edges
├── agents/
│   ├── base_agent.py    Abstract BaseAgent — all agents inherit this
│   ├── sponsor_agent.py      [P2 — to implement]
│   ├── speaker_agent.py      [P2 — to implement]
│   ├── exhibitor_agent.py    [P2 — to implement]
│   ├── revenue_agent.py      [P2 — to implement]
│   ├── venue_agent.py        [P3 — to implement]
│   ├── pricing_agent.py      [P3 — to implement]
│   ├── community_gtm_agent.py [P5 — to implement]
│   └── event_ops_agent.py    [P5 — to implement]
├── memory/
│   ├── vector_store.py  ChromaDB (local) / Pinecone (prod) — semantic search
│   └── postgres_store.py Async Supabase/asyncpg — structured event data
├── models/
│   ├── schemas.py       All Pydantic models + AgentState + EventConfigInput
│   └── pricing_model.py AttendancePredictor (sklearn)
├── tools/               [fully implemented — see backend/tools/README.md]
└── templates/
    └── sponsorship_proposal.html   Jinja2 PDF template
```

---

## How Data Flows

```
User (Next.js form)
    │  POST /api/run-plan  {category, geography, audience_size, budget_usd, event_dates}
    ▼
FastAPI main.py
    │  validates EventConfigInput via Pydantic, passes to orchestrator
    ▼
orchestrator.py  (LangGraph StateGraph)
    │  initialises blank AgentState
    │
    ├──► venue_agent.run(state)       ┐  parallel
    ├──► sponsor_agent.run(state)     │  fan-out
    └──► speaker_agent.run(state)     ┘
              │
              ▼
         exhibitor_agent.run(state)
              │
              ▼
         pricing_agent.run(state)
              │
              ▼
         community_gtm_agent.run(state)
              │
              ▼
         event_ops_agent.run(state)
              │
              ▼
         revenue_agent.run(state)
              │
              ▼
    Final AgentState (all fields populated)
    │
    ▼
FastAPI returns JSON → Next.js Dashboard renders output
```

---

## `schemas.py` — Contracts

### `EventConfigInput`

User's form submission. Fields that agents READ (never write):

| Field | Type | Example |
|---|---|---|
| `category` | `str` | `"AI"` |
| `geography` | `str` | `"Europe"` |
| `audience_size` | `int ≥ 1` | `800` |
| `budget_usd` | `float ≥ 0` | `50000.0` |
| `event_dates` | `str` (ISO 8601) | `"2025-09-15"` |
| `event_name` | `str` (optional) | `""` → agents default to `"{category} Summit"` |

### `AgentState`

TypedDict flowing through the LangGraph graph. Each agent owns one or more fields:

| Field | Owned by | Type |
|---|---|---|
| `event_config` | orchestrator (init) | `EventConfigInput` |
| `sponsors` | Sponsor Agent | `list[SponsorSchema]` |
| `speakers` | Speaker Agent | `list[SpeakerSchema]` |
| `venues` | Venue Agent | `list[VenueSchema]` |
| `exhibitors` | Exhibitor Agent | `list[ExhibitorSchema]` |
| `pricing` | Pricing Agent | `list[TicketTierSchema]` |
| `communities` | Community GTM Agent | `list[CommunitySchema]` |
| `schedule` | Event Ops Agent | `list[dict]` |
| `revenue` | Revenue Agent | `dict` |
| `gtm_messages` | Community GTM Agent | `dict[str, str]` |
| `messages` | all agents (LLM history) | `list` |
| `errors` | any agent | `list[str]` |
| `metadata` | any agent (extras) | `dict` |

---

## `base_agent.py` — Agent Contract

Every specialized agent must:

1. **Inherit** `BaseAgent`
2. **Set** `name: str = "your_agent_name"` — must match the node name in `orchestrator.py`
3. **Set** `tools: ClassVar[list[Any]] = [your_lc_tools]`
4. **Override** `_build_prompt() -> ChatPromptTemplate`
5. **Override** `run(state: AgentState) -> AgentState`

### Minimal subclass skeleton

```python
from backend.agents.base_agent import BaseAgent
from backend.models.schemas import AgentState

class SponsorAgent(BaseAgent):
    name = "sponsor_agent"

    def _build_prompt(self):
        from langchain_core.prompts import ChatPromptTemplate
        return ChatPromptTemplate.from_messages([
            ("system", "You are a sponsor discovery specialist..."),
            ("human", "{input}"),
        ])

    def run(self, state: AgentState) -> AgentState:
        try:
            cfg = state["event_config"]
            # ... call tools, produce sponsors ...
            state["sponsors"] = []
        except Exception as exc:
            state = self._log_error(state, str(exc))
        return state
```

### Helper methods available for free

| Method | What it does |
|---|---|
| `self._get_llm()` | Returns `ChatOpenAI(gpt-4o-mini)` bound to `self.tools` |
| `self._read_memory(query, collection, k)` | Vector store similarity search |
| `self._write_memory(docs, metadata, collection)` | Embed + store in vector store |
| `self._log_error(state, message)` | Appends to `state["errors"]`, returns state |

---

## `orchestrator.py` — Graph Topology

The graph is compiled once at import time (`graph = _build_graph()`).

- Agents are imported lazily — if your module doesn't exist yet, a passthrough node is used so the graph still compiles.
- `run_plan(config)` is the main async entry point called by FastAPI.
- `_initial_state(config)` creates a blank state — no field will ever be missing.

### How to add your agent

1. Create `backend/agents/your_agent.py` with class `YourAgent(BaseAgent)` and `name = "your_agent"`
2. The orchestrator's `_import_agents()` already has a lazy import for your module — **no changes needed to orchestrator.py**.

---

## `main.py` — REST API

| Route | Method | Purpose |
|---|---|---|
| `/api/run-plan` | `POST` | Invoke full pipeline, returns complete plan JSON |
| `/api/agent-status?plan_id=...` | `GET` | SSE stream of agent progress |
| `/api/output/{plan_id}` | `GET` | Retrieve a saved plan by UUID |
| `/health` | `GET` | Liveness probe for Railway/Render |

Swagger UI: `http://localhost:8000/docs` (runs when you start the server).

**To start locally (inside venv)**:
```bash
uvicorn backend.main:api --reload --port 8000
```

---

## `memory/vector_store.py` — Semantic Memory

| Function | Purpose |
|---|---|
| `embed_and_store(docs, metadata, collection)` | Embed text + upsert into ChromaDB/Pinecone |
| `similarity_search(query, collection, k)` | Return k most similar docs |

Collections agents use:

| Collection | Who writes | Who reads |
|---|---|---|
| `"events"` | P3 dataset seeding script | Pricing Agent, Revenue Agent |
| `"sponsors"` | Sponsor Agent | Sponsor Agent (cross-run caching) |
| `"speakers"` | Speaker Agent | Speaker Agent |
| `"venues"` | Venue Agent | Venue Agent |

Switch to Pinecone in production: `USE_PINECONE=true` in `.env`.

---

## `memory/postgres_store.py` — Structured Storage

| Function | Purpose |
|---|---|
| `save_event(event)` | Upsert one EventSchema → returns UUID |
| `get_events(filters)` | SELECT with optional WHERE filters |
| `save_plan(state)` | Store full AgentState as JSONB → returns UUID |

**To set up Supabase**:
1. Create a new Supabase project
2. Run `dataset/supabase_schema.sql` in Supabase SQL Editor
3. Add `DATABASE_URL` to `.env`

---

## What Each Teammate Should Know Before Starting

### P2 (Sponsor/Speaker/Exhibitor/Revenue Agents)

- Read `backend/tools/README.md` for exact function signatures
- Import tools from `backend/tools/` — **do not re-implement** search or scraping
- Your agent must set `state["sponsors"]` / `state["speakers"]` / etc. and return the full state
- Call `self._log_error(state, str(e))` on any exception — never let an exception propagate up

### P3 (Venue/Pricing Agents + Dataset)

- Use `scraping/scrapegraph_runner.py` for data collection (see `scraping/README.md`)
- Normalise all records with `scraping/etl_pipeline.normalize_event(raw)` before saving
- `AttendancePredictor` in `backend/models/pricing_model.py` is ready — just call `.train(df)` then `.predict(...)`
- Fill `dataset/events_2025_2026.csv` with ≥100 rows; schema is in `dataset/dataset_documentation.md`

### P4 (Frontend)

- Call `POST /api/run-plan` with the `EventConfigInput` fields
- Poll `GET /api/agent-status?plan_id=<id>` for progress (SSE)
- Render from `GET /api/output/{plan_id}` — field names match the `AgentState` TypedDict exactly
- All Pydantic model field names are documented in `backend/models/README.md`

### P5 (Community GTM + Event Ops)

- `search_communities(topic)` from `serper_tool.py` is your data source for GTM agent
- Event Ops agent: read `state["speakers"]` and `state["venues"]`, produce `state["schedule"]` as `[{time, room, speaker, topic}]`
- No LLM needed for conflict detection — pure Python greedy scheduling is enough
