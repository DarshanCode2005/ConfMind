# Agents — Internal Documentation

Quick reference for every agent in `backend/agents/`.  
All agents inherit `BaseAgent` and are wired into the LangGraph orchestrator via `backend/orchestrator.py`.

---

## Shared Contracts

### `BaseAgent` (abstract)

Every agent must implement:

| Method | Signature | Description |
|---|---|---|
| `_build_prompt()` | `-> ChatPromptTemplate` | System + human prompt for the agent's LLM role |
| `run(state)` | `AgentState -> AgentState` | Main entry point; reads inputs, writes outputs |

Optional overrides:

| Attribute / Method | Default | Description |
|---|---|---|
| `name: str` | `"base_agent"` | Unique node name used by LangGraph |
| `tools: list` | `[]` | LangChain tools bound to the LLM |
| `_get_llm(temperature)` | `gpt-4o-mini` | Override to swap model or temperature |

**Inherited helpers** (do NOT override):

| Method | Returns | Description |
|---|---|---|
| `_read_memory(query, collection, k)` | `list[dict]` | Similarity search in ChromaDB / Pinecone |
| `_write_memory(docs, metadata, collection)` | `None` | Embed + upsert into vector store |
| `_log_error(state, message)` | `AgentState` | Appends to `state["errors"]`; keeps graph running |

**Error handling convention**: Wrap the entire `run()` body in `try/except Exception as exc` and call `self._log_error(state, str(exc))` so that a failing agent does not halt the whole pipeline.

---

## `SponsorAgent`

**File**: [`sponsor_agent.py`](./sponsor_agent.py)  
**LangGraph node name**: `sponsor_agent`  
**Uses LLM**: No (fully rule-based scoring)  
**Reads from state**: `event_config`  
**Writes to state**: `sponsors`, `metadata`

### What It Does

1. **Fetches** sponsor candidates from two sources:
   - `search_sponsors_structured(category, geo)` via ScrapeGraph-AI → `list[SponsorSchema]`
   - `search_sponsors(category, geo)` via Serper → `list[SerperResult]` (converted to bare stubs)
2. **Deduplicates** by `name` (case-insensitive exact match).
3. **Scores** each sponsor with a deterministic formula — no LLM call:

   | Component | Max | Rule |
   |---|---|---|
   | `industry_relevance` | 10 | `10` if category keyword inside `sponsor.industry`; `5` partial; `2` no match |
   | `geo_match` | 5 | `5` if `sponsor.geo == event geography`; else `0` |
   | `tier_bonus` | 5 | Gold=5, Silver=3, Bronze=1, General=0 |

   Raw score (0-20) is normalised → `relevance_score` (0-10) to stay within `SponsorSchema` bounds.

4. **Ranks** descending by `relevance_score`, keeps top 10.
5. **Generates PDF proposals** (`save_proposal`) for the top 3 and stores absolute paths in `state["metadata"]["proposal_<name>"]`.

### Scoring Helper (private)

```python
# backend/agents/sponsor_agent.py
def _score_sponsor(sponsor: SponsorSchema, category: str, geography: str) -> float:
    """Returns raw score in [0, 20]. Normalise to [0, 10] before storing."""
```

### Usage

```python
from backend.agents.sponsor_agent import SponsorAgent

agent = SponsorAgent()
updated_state = agent.run(state)
top_sponsors = updated_state["sponsors"]        # list[SponsorSchema], sorted by score
proposals    = updated_state["metadata"]        # {"proposal_TechCorp": "/abs/path.pdf", ...}
```

### Configuration

| Constant | Default | Description |
|---|---|---|
| `_TOP_N` | `10` | Maximum sponsors kept in `AgentState.sponsors` |
| `_PROPOSAL_TOP` | `3` | Number of PDF proposals generated |

### Tests

Test file: [`tests/test_sponsor_agent.py`](../../tests/test_sponsor_agent.py)  
Run: `pytest tests/test_sponsor_agent.py -v` — **11 tests, all mocked** (no API keys needed).

| Test | Description |
|---|---|
| `test_score_sponsor_full_match` | Gold + exact industry + exact geo → raw score 20 |
| `test_score_sponsor_partial_industry_match` | Partial keyword → industry_score=2, not 10 |
| `test_score_sponsor_no_geo_match` | Geo mismatch → 0 out of 5 |
| `test_score_sponsor_general_tier` | General tier → 0 tier bonus |
| `test_sponsor_agent_run_returns_agent_state` | `run()` returns dict with `sponsors` key |
| `test_sponsor_agent_sponsors_are_sorted_by_score` | Output is sorted descending by score |
| `test_sponsor_agent_deduplicates_serper_and_scraper_results` | Same name not duplicated |
| `test_sponsor_agent_saves_proposals_for_top_3` | `save_proposal` called ≤ 3 times |
| `test_sponsor_agent_proposal_paths_stored_in_metadata` | Paths recorded in `metadata` |
| `test_sponsor_agent_handles_empty_results` | Both tools return `[]` → `sponsors=[]`, no error |
| `test_sponsor_agent_logs_error_on_tool_exception` | Tool raises → error appended to `state["errors"]` |

---

## `SpeakerAgent`

**File**: [`speaker_agent.py`](./speaker_agent.py)  
**LangGraph node name**: `speaker_agent`  
**Uses LLM**: Yes — per-speaker agenda topic mapping (`gpt-4o-mini`, temperature 0.3)  
**Reads from state**: `event_config`  
**Writes to state**: `speakers`

### What It Does

1. **Fetches** speakers via `search_speakers_structured(category, geography)` (ScrapeGraph-AI)
2. **Enriches** each speaker with a LinkedIn influence score via `enrich_speakers()`:
   - Speakers without `linkedin_url` are skipped gracefully (score stays 0.0)
   - Per-speaker LinkedIn errors are non-fatal (enrichment continues for the rest)
3. **Maps topics** — one LLM call per speaker via `_map_topic(chain, theme, speaker)`:
   - Input: event theme + speaker name, bio, current topic
   - Output: refined agenda topic (max 10 words), aligned with the event theme
   - Falls back to original topic if LLM raises (non-fatal)
4. **Sorts** descending by `influence_score` (no top-N cap; EventOpsAgent handles scheduling)

### LLM Prompt

```
system: "You are a conference agenda specialist. Given an event theme and a speaker's
         name, bio, and current topic, return a single refined agenda topic (maximum
         10 words) that best fits the event theme. Respond with ONLY the topic string."
human:  "Event theme: {theme}\nSpeaker: {name}\nBio: {bio}\nCurrent topic: {topic}"
```

### Influence Score Formula (from `linkedin_tool.py`)

```
follower_pts  = log10(followers + 1) / log10(100_001) * 6.0   (max 6)
posts_pts     = min(posts, 10) / 10 * 2.0                      (max 2)
conn_pts      = min(connections, 500) / 500 * 2.0              (max 2)
influence_score = follower_pts + posts_pts + conn_pts          (max 10)
```

### Private Helper

```python
def _map_topic(chain: Any, theme: str, speaker: SpeakerSchema) -> str:
    """Invoke the LLM chain; falls back to speaker.topic on any exception."""
```

### Usage

```python
from backend.agents.speaker_agent import SpeakerAgent

agent = SpeakerAgent()
updated_state = agent.run(state)
speakers = updated_state["speakers"]    # list[SpeakerSchema], sorted by influence_score
```

### Tests

Test file: [`tests/test_speaker_agent.py`](../../tests/test_speaker_agent.py)  
Run: `pytest tests/test_speaker_agent.py -v` — **9 tests, all mocked**.

| Test | Description |
|---|---|
| `test_map_topic_returns_llm_content` | `_map_topic` strips and returns LLM `.content` |
| `test_map_topic_falls_back_on_exception` | `_map_topic` returns original topic when LLM raises |
| `test_speaker_agent_run_returns_agent_state` | `run()` returns dict with `speakers` key |
| `test_speaker_agent_speakers_sorted_by_influence` | Output sorted descending by `influence_score` |
| `test_speaker_agent_enrich_speakers_called` | `enrich_speakers` called once with scraper output |
| `test_speaker_agent_topic_mapped_via_llm` | Speaker topic updated to `_map_topic` return value |
| `test_speaker_agent_handles_llm_topic_failure` | `_map_topic` exception caught by outer try/except → error logged |
| `test_speaker_agent_handles_empty_scraper_result` | Empty list → `speakers=[]`, no errors |
| `test_speaker_agent_logs_error_on_scraper_exception` | Scraper raises → `state["errors"]` non-empty |

---

## Upcoming Agents

> The following agents are planned but not yet implemented.

| Agent | Node Name | Writes to | Owner |
|---|---|---|---|
| `SpeakerAgent` | `speaker_agent` | `state["speakers"]` | P2 |
| `ExhibitorAgent` | `exhibitor_agent` | `state["exhibitors"]` | P2 |
| `RevenueAgent` | `revenue_agent` | `state["revenue"]` | P2 |
| `VenueAgent` | `venue_agent` | `state["venues"]` | P3 |
| `PricingAgent` | `pricing_agent` | `state["pricing"]` | P3 |
| `CommunityGTMAgent` | `community_gtm_agent` | `state["communities"]`, `state["gtm_messages"]` | P5 |
| `EventOpsAgent` | `event_ops_agent` | `state["schedule"]` | P5 |

Add a new section to this file for each agent as it is implemented.
