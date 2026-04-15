Let me design this architecture diagram first, then give you the full prompt spec.---

## Recent Architecture & Codebase Changes (April 2026)
- **Vector Store Optimization:** Switched `vector_store.py` to use `OpenAIEmbeddingFunction` (and tested `OllamaEmbeddingFunction`) to bypass the massive 1GB default ONNX downloads.
- **PredictHQ 400 Fixes:** Changed `place__scope` to `q` across `web_search_agent.py`, `venue_agent.py`, and `community_gtm_agent.py` so standard city strings (e.g. "San Francisco, CA") resolve correctly without throwing 400 Bad Request.
- **LLM Fallback Refactoring:** Configured `BaseAgent._get_llm()` to prioritize `google/gemma-2-27b-it` and `google/gemma-2-9b-it` via OpenRouter, with a seamless tertiary fallback to local Ollama (`confmind-planner`).
- **Ollama Local JSON Enforcement:** Updated `backend/agents/Modelfile` with strict system instructions to guarantee JSON parsing stability when using local Gemma4 models.
- **Agent Output Parsing:** Refactored `community_gtm_agent.py` to request `{ "messages": [...] }` instead of a naked array to dramatically improve JSON parsing reliability for smaller local models.
- **Schema Validation:** Fixed `models/schemas.py` `VenueSchema` by setting `city: str | None = None` and `country: str | None = None` to prevent Pydantic validation crashes when fields are null.
- **Orchestrator Graph Integration:** Fixed a critical structural bug in `orchestrator.py` by incorporating `WebSearchAgent` immediately after the `START` node, so that `past_events` are properly acquired and passed downstream to the rest of the fanned-out agents.
- **Env & Git Hygiene:** Created `.env.example` with standard API keys formats and added `.venv/` to `.gitignore`.

---
## .env keys to add

```
TAVILY_API_KEY=
PREDICTHQ_API_KEY=
OPENROUTER_API_KEY=
LANGSMITH_API_KEY=        # optional, for tracing
```

---

## Coding agent prompt — full system spec

Paste this verbatim to your coding agent as the implementation brief:

---

**CONFMIND — Agent Behavior Specification**

**Shared state**: Every agent reads from and writes delta-updates to a single `AgentState` object. Core keys: `past_events` (list), `sponsors`, `speakers`, `venues`, `exhibitors`, `pricing`, `gtm`, `schedule`, `revenue`, `errors` (operator.add), `metadata` (operator.ior). Agents return only the keys they modify.

**Shared memory**: ChromaDB instance. Agents call `_write_memory(key, content)` after each pass and `_read_memory(query)` at the start of each pass. Memory is append-only during a run.

**Tool contracts**:
- Tavily tool: call with `search_depth="advanced"`, `max_results=5`. Returns list of `{url, content, score}`. Always use the `content` field, never fetch URLs separately.
- PredictHQ Events tool: wrap the official Python SDK `phq.events.search(...)`. Always request fields: `title, category, phq_attendance, predicted_event_spend, entities, location, start, rank`. Paginate with `limit=10`.
- PredictHQ Features tool: wrap `POST /v1/features/` SDK call. Request `phq_attendance_conferences`, `phq_attendance_sports`, `phq_spend_conferences`, `phq_rank_public_holidays` minimum.

---

### 1. Main Orchestrator (LangGraph Supervisor node)

**Behavior**:
1. Receive input `{category, geography, target_size, budget}`. Map `category` to PredictHQ category strings: `Technical Conference → conferences`, `Music Festival → concerts,festivals`, `Sports → sports`, `Educational Conference → conferences,expos`.
2. **Probe PredictHQ** — call Events API with mapped category + geography + `active.gte=2025-01-01`. Get `total` count from response. Do NOT retrieve full results yet.
3. **Decide N** — `N = min(max(3, total // 5), 8)`. If total < 5, set N = total or 3 (whichever is higher). Each web-search agent is assigned `ceil(total / N)` events via offset pagination.
4. Spawn N web-search agents as parallel LangGraph nodes with their assigned offset ranges. Wait for all to complete before proceeding.
5. Consolidate their outputs into `past_events` list in state. Deduplicate by event title + location hash.
6. Load skill file from memory for the input category → determine which specialized agents to run and in what order. Default order: `[Sponsor, Speaker, Venue]` parallel → `Exhibitor` → `[Pricing, GTM]` parallel → `EventOps` → `Revenue`.
7. Pass control to the first tier. Each tier receives the full current state.

**Retry**: If PredictHQ probe fails (non-200), fall back to N=4 fixed and instruct web-search agents to use Tavily only. Log to `errors`.

**Stop condition**: All specialized agents return without error OR 2 full retry passes exhausted.

---

### 2. Web Search Agent (spawned N times in parallel)

**Role**: Given assigned offset range, fetch past event records and extract structured data.

**Loop**:
- Pass 1 (PredictHQ primary): Call Events API with assigned offset. For each event, extract: `title, location, category, phq_attendance, predicted_event_spend, entities` (look for `type=venue`, `type=performer`, `type=organizer` sub-fields), `start`, `rank`.
- Pass 2 (enrichment): For each event where `phq_attendance` is null OR `entities` is empty → run Tavily query `"{event_title} {year} sponsors speakers exhibitors"`. Parse content for sponsor names, speaker names, ticket pricing mentions.
- Pass 3 (pricing only): If no pricing found in Pass 2 → run Tavily query `"{event_title} ticket price"`. Extract any numeric pricing mention via regex `\$[\d,]+` or `₹[\d,]+` or `€[\d,]+`.

**Output per event** (dict): `{name, location, category, sponsors: [], speakers: [], exhibitors: [], venue_name, pricing: {}, attendance_estimate, phq_rank, source}`. Fields missing after 3 passes → set to `null`, do not retry further.

**Stop**: All assigned events processed OR 3 passes per event completed. Write output to `past_events` in state.

**Error handling**: PredictHQ 429 → wait 2s, retry once. PredictHQ 401 → log to `errors`, switch to Tavily-only for remaining events.

---

### 3. Sponsor Agent

**Role**: Discover, score, and rank sponsors. Generate draft proposals for top 3.

**Loop**:
- Pass 1 (extraction, no tools): Iterate `past_events`, collect all sponsor names. Deduplicate. Build initial dict `{name, seen_in_events: [], category: null, geography: null, spend_proxy: null}`.
- Pass 2 (enrichment via Tavily): For each unique sponsor, run one Tavily query: `"{sponsor_name} event sponsorship {geography} 2025"`. Extract: industry category, headquarters country, any sponsorship dollar amount mentioned. Cap at top 20 sponsors by frequency before doing Pass 2.
- Pass 3 (scoring): Score each sponsor: `score = 0.35 * industry_relevance + 0.25 * geography_match + 0.25 * frequency_normalized + 0.15 * spend_proxy_normalized`. `industry_relevance` = LLM call comparing sponsor category to input event category (0–1). `geography_match` = 1 if same country else 0.5 if same continent else 0. `frequency_normalized` = seen_in_events count / max count in set. `spend_proxy_normalized` = log(spend_usd+1) / 15 capped at 1.
- Pass 4 (proposals): For top 3 sponsors by score, generate a custom sponsorship proposal using an LLM call with template: `{event_name, sponsor_name, industry_relevance_reason, proposed_tier, estimated_reach (from Pricing Agent if available else target_size)}`. Output as markdown string.

**Stop**: Top 15 sponsors scored. If Pass 2 yields no enrichment for a sponsor after 1 retry with a broader query (`"{sponsor_name} marketing spend"`) → keep sponsor with partial data.

**Output**: `sponsors` key in state — list of dicts sorted by score descending. Top 3 include `proposal_md` field.

---

### 4. Speaker Agent

**Role**: Discover and score speakers/artists. Map to agenda topics.

**Loop**:
- Pass 1 (extraction, no tools): Collect all speakers/performers from `past_events`. Build initial records `{name, past_events: [], topics: []}`.
- Pass 2 (profile enrichment via Tavily): For each speaker, run Tavily query `"{speaker_name} speaker {category} LinkedIn"`. Extract: follower count (look for "K followers" or "connections"), publications count, most recent speaking gig year, primary topic tags. If name is ambiguous (common name), append event name to query.
- Pass 3 (scoring): `influence_score = 0.4 * topic_match + 0.3 * follower_norm + 0.2 * past_speaking_norm + 0.1 * publications_norm`. `topic_match` = LLM cosine-sim proxy between speaker topics and input event category (0–1). Normalize follower and speaking counts against set max.
- Pass 4 (expansion): If total scored speakers < 10 → run Tavily query `"top speakers {category} conference {geography} 2025 2026"`. Extract new names not already in list. Run abbreviated Pass 2+3 for new names. Limit 1 expansion round.
- Pass 5 (agenda mapping): LLM call — given final speaker list and event category, suggest 6–10 agenda topics and map 1–3 speakers per topic. Output as `{topic: str, speakers: [str], slot_duration_mins: int}`.

**Stop**: ≥15 speakers scored OR 2 expansion rounds completed.

**Output**: `speakers` in state — list sorted by score. Plus `agenda_draft` list in `metadata`.

---

### 5. Venue Agent

**Role**: Recommend venues ranked by fit.

**Loop**:
- Pass 1 (PredictHQ history): Query Events API for past events in target geography filtered by `category`. Extract all `entities` of `type=venue`. Collect: `{name, location, capacity_hint: null, past_event_count: 0}`.
- Pass 2 (Tavily enrichment): For each venue name, run Tavily query `"{venue_name} {city} capacity events"`. Extract: capacity number, pricing tier (affordable/mid/premium), any notable past events hosted.
- Pass 3 (new candidates): Run Tavily query `"best venues {city} conference {target_size} attendees"`. Extract venue names not already in list. Append and do abbreviated Pass 2.
- Pass 4 (ranking): Score: `fit_score = 100 - abs(capacity - target_size)/target_size * 50 + past_event_count * 5 - cost_tier_penalty`. `cost_tier_penalty`: premium=20, mid=10, affordable=0 if budget constraint is set, else 0.

**Stop**: ≥5 venues ranked OR geography radius expanded once (e.g., city → region) and still <5.

**Output**: `venues` in state — top 5 as list of dicts.

---

### 6. Exhibitor Agent

**Role**: Cluster exhibitors by category.

**Loop**:
- Pass 1 (extraction, no tools): Collect all exhibitor mentions from `past_events`. Many will be null — that is expected.
- Pass 2 (clustering via LLM): For each exhibitor, LLM call classifies into: `startup`, `enterprise`, `tools_platform`, `media`, `individual`, `government`. Allow multi-label. Build cluster dict.
- Pass 3 (gap fill): For clusters with < 2 members → run one Tavily query: `"{category} conference exhibitors {cluster_name} {geography} 2025"`. Extract names, run classification. One query per empty cluster, max 3 queries total.

**Stop**: All clusters have ≥ 1 member OR 1 gap fill round completed. Do not loop further.

**Output**: `exhibitors` in state — `{cluster_name: [exhibitor_dicts]}`.

---

### 7. Pricing & Footfall Agent

**Role**: Predict optimal ticket pricing and expected attendance. No ML models — use historical interpolation only.

**Data sources** (no loop, sequential):
- Step 1: Extract `(attendance_estimate, pricing)` pairs from `past_events` where both are non-null.
- Step 2: Call PredictHQ Features API for target geography + target event date range (if provided, else use next 6 months). Request: `phq_attendance_conferences`, `phq_spend_conferences`. Get the `sum` stat for the target month.
- Step 3: Compute `demand_ratio = phq_attendance_sum / avg_historical_attendance`. If Features API unavailable → `demand_ratio = 1.0`.
- Step 4: `expected_attendance = weighted_avg(historical_attendances) * demand_ratio`. Weight recent events higher (decay factor 0.85 per year back).
- Step 5: Derive pricing tiers from historical pricing distribution: `early_bird = p25`, `general = p50`, `vip = p75` of historical price list. If no historical pricing → use formula: `general = target_budget / (expected_attendance * 0.6)`.
- Step 6: Monte Carlo confidence interval — sample attendance from `Normal(expected_attendance, 0.2 * expected_attendance)` for 200 iterations. Report p10/p50/p90.
- Step 7: Revenue projection — `total_revenue = early_bird * 0.3 * att_p50 + general * 0.55 * att_p50 + vip * 0.15 * att_p50 + sum(sponsor scores top 5 * 5000)` (sponsor revenue proxy).
- Step 8: Break-even analysis — `break_even_attendees = total_fixed_cost / (general - variable_cost_per_head)`. Use `total_fixed_cost = budget * 0.6` and `variable_cost_per_head = general * 0.15` as defaults if not provided.

**Output**: `pricing` in state — `{early_bird, general, vip, expected_attendance: {p10, p50, p90}, revenue_projection, break_even_attendees}`.

---

### 8. Community & GTM Agent

**Role**: Find distribution channels and generate promotion messaging.

**Loop**:
- Pass 1 (community discovery via Tavily): Run 3 queries in parallel: `"Discord server {category} community"`, `"Slack group {category} professionals"`, `"Reddit community {category} events"`. Extract community names, platform, estimated member count, invite link if available.
- Pass 2 (LinkedIn/Facebook via Tavily): Run `"LinkedIn group {category} {geography}"` and `"Facebook group {category} conference"`. Extract same fields.
- Pass 3 (categorization): LLM classifies each community into niche tags matching the event category. Score relevance 0–1.
- Pass 4 (timing via PredictHQ): Query PredictHQ Events API for upcoming events in target geography within 90 days. Identify demand peaks (events with `rank > 70`). Schedule GTM promotion to start 45 days before nearest demand peak OR 60 days before event date, whichever is sooner.
- Pass 5 (message generation): LLM generates 3 message variants per channel type (Discord announcement, LinkedIn post, cold email). Each variant: ≤150 words, includes event name/category/date placeholder, tailored to channel tone.

**Stop**: ≥10 communities found across platforms OR 2 search rounds done per platform.

**Output**: `gtm` in state — `{communities: [], promotion_timeline, message_variants: {discord, linkedin, email}}`.

---

### 9. Event Ops Agent

**Role**: Build a conflict-free hour-by-hour schedule.

**Behavior** (no external tools):
- Read `agenda_draft` from `metadata` (from Speaker Agent) and `venues` from state.
- Assume event duration from `target_size`: <200 → 1 day, 200–1000 → 2 days, >1000 → 3 days.
- LLM call: Given agenda topics + speaker list + day count, generate time slots as `{day, start_time, end_time, title, speaker, room, type: keynote|panel|workshop|break|networking}`.
- Conflict detection: After generation, check for: same speaker in overlapping slots, same room double-booked, back-to-back sessions with no break > 3 hours. If conflict found → LLM call to resolve only the conflicting slots (not full regeneration).
- Resource planning: Assign rooms if venue has multiple (from `venues[0].capacity`) — large sessions get main hall, workshops get breakout rooms.

**Stop**: Conflict-free schedule produced OR 3 resolve attempts. On 3rd failure → flag unresolved conflicts in `errors` and output best-effort schedule.

**Output**: `schedule` in state — list of slot dicts sorted by day + start_time.

---

### 10. Revenue Agent

**Role**: Final financial summary. No tools.

Aggregate from state: `pricing.revenue_projection`, `pricing.break_even_attendees`, sponsor count × avg tier value (tier 1 = ₹2L, tier 2 = ₹75k, tier 3 = ₹25k as defaults), exhibitor count × ₹15k booth fee default. Compute: Total Revenue, Total Cost (budget input or estimated), Profit, ROI%. Output as `revenue` dict in state.

---

### Global retry / stop rules (apply to all agents)

- **Tavily 429**: Wait 3s, retry once. If fails again → skip that query, mark field as null, continue.
- **PredictHQ 401/403**: Switch to Tavily-only for all remaining queries in that agent. Log once.
- **LLM empty response**: Retry once with `temperature=0`. On second empty → use fallback hardcoded value or skip that field.
- **Any agent exception**: Catch, log to `errors`, return partial state with whatever was completed. Orchestrator continues to next agent rather than halting the graph.
- **No agent should call another agent's tools** — they only read shared state and call their own assigned tools.
- **Max total graph execution time**: Set `timeout=300s` on the LangGraph runner. If hit → return whatever state has been populated so far.