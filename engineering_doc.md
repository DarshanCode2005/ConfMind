# ConfMind Engineering Documentation

## 1. Overview

ConfMind is a production-grade, domain-agnostic, multi-agent event orchestration platform. It supports four event categories: Sports Events, Music Festivals, Technical Conferences, and Educational Conferences. The system leverages LangGraph for agent orchestration, ChromaDB for persistent memory, and integrates with PredictHQ and Tavily for event intelligence and enrichment. All agent behaviors, tool contracts, and memory protocols strictly follow the 2026 High-Prep Project specification.

## 2. System Architecture

- **Frontend**: Next.js 14 dashboard (optional Streamlit UI for demo)
- **Backend**: FastAPI API gateway
- **Agent Orchestration**: LangGraph (Python)
- **Memory**: ChromaDB (vector DB, persistent, append-only per run)
- **External APIs**: PredictHQ (official SDK), Tavily (search, advanced mode)
- **Skill Files**: 4 JSON files in `/skills/` (one per event category)

### Agent Hierarchy
- Orchestrator (supervisor, dynamic agent spawning)
- Web Search Agents (N parallel, event data extraction)
- Sponsor, Speaker, Venue, Exhibitor, Pricing, GTM, EventOps, Revenue Agents (see below)

## 3. Shared State & Memory

- **AgentState**: TypedDict with keys: `past_events`, `sponsors`, `speakers`, `venues`, `exhibitors`, `pricing`, `gtm`, `schedule`, `revenue`, `errors`, `metadata`.
- **Memory Protocol**: Every agent reads memory at the start of each pass (`_read_memory(query)`), writes delta at end (`_write_memory(key, content)`). Memory is append-only during a run. Memory Curator sub-agent consolidates every 5 turns.

## 4. Skill Files

- 4 JSON files in `/skills/` (one per category)
- Each contains: `agent_order`, `category_mapping_to_phq`, `tavily_query_templates`, `spawn_logic_hints`
- Orchestrator loads the correct file based on user input

## 5. Tool Contracts

- **Tavily**: Always use `search_depth="advanced"`, `max_results=5`, only the `content` field. No direct URL fetches. Queries must be category-aware.
- **PredictHQ Events**: Use official SDK, always request fields: `["title","category","phq_attendance","predicted_event_spend","entities","location","start","rank","place_hierarchies"]`, paginate with `limit=10`.
- **PredictHQ Features**: Use for demand_ratio only, POST `/v1/features/` with minimum required fields.

## 6. Agent Specifications

### Orchestrator
- Receives user input, maps category, probes PredictHQ for event count, dynamically spawns N Web Search Agents, deduplicates results, loads skill file, determines agent order, manages retries/timeouts, returns partial state on error.

### Web Search Agent
- Extracts past events using PredictHQ, enriches with Tavily, fills missing pricing, outputs structured event dicts.

### Sponsor Agent
- Extracts, enriches, scores, and proposes sponsors using historical data and Tavily enrichment.

### Speaker Agent
- Discovers, scores, and maps speakers to agenda topics, prioritizing past speakers, expands with Tavily if needed.

### Venue Agent
- Extracts venues from PredictHQ, enriches with Tavily, scores and ranks top venues.

### Exhibitor Agent
- Clusters exhibitors from past events, gap-fills with Tavily if needed.

### Pricing & Footfall Agent
- Uses historical interpolation and PredictHQ Features for pricing, no ML models.

### Community & GTM Agent
- Focuses on Discord and other communities, uses Tavily and PredictHQ for timing, generates GTM messages.

### Event Ops Agent
- Builds conflict-free schedule using agenda and venues, resolves conflicts.

### Revenue Agent
- Aggregates totals, profit, ROI% from state, no external tools.

## 7. Error Handling & Fallbacks

- Tavily 429: wait 3s, retry once, then skip
- PredictHQ 401/429: switch to Tavily-only, log once
- LLM empty: retry once (temp=0), fallback null
- No inter-agent tool calls
- Partial output on error, orchestrator continues
- Max graph time 300s, return whatever state exists

## 8. Output

- Final output: structured JSON, markdown plan for UI/demo, sources for mandatory dataset (PredictHQ + Tavily)

## 9. Repository Structure

- See README for full structure. Key folders: `/backend/agents/`, `/backend/tools/`, `/backend/models/`, `/skills/`, `/dataset/`, `/frontend/`

## 10. Development & Commit Guidelines

- Follow Conventional Commits (see README)
- Lint/type-check: `npm run lint:py`, `npm run format:py`, `npm run typecheck:py`
- All agent logic, tool use, and memory protocols must strictly follow the AGENTS.md and this engineering doc.

---

For further details, see AGENTS.md and README.md.
