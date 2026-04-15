# ConfMind Agentic System — Internal Documentation

This directory contains the core logic for the **ConfMind** multi-agent orchestration. The system uses a directed acyclic graph (DAG) managed by **LangGraph** to process event requirements and generate a complete conference plan.

---

## 🏗️ System Architecture

The orchestration follows a **Hierarchical Parallel** topology:
1. **Discovery (Parallel)**: `VenueAgent`, `SponsorAgent`, and `SpeakerAgent` run concurrently to gather foundational data.
2. **Expansion**: `ExhibitorAgent` uses discovered data to identify partners.
3. **Strategy**: `PricingAgent` calculates costs and ticket tiers.
4. **Outreach**: `CommunityGTMAgent` generates GTM messages and finds distribution channels.
5. **Logistics**: `EventOpsAgent` builds a detailed hour-by-hour schedule.
6. **Financials**: `RevenueAgent` computes final ROI and profit/loss statements.

---

## 🧠 Brain & State Management

### Multi-Model Fallback Strategy
All agents use a resilient LLM connection via `BaseAgent._get_llm()`:
- **Primary**: `google/gemma-2-27b-it` (OpenRouter) — Highest reasoning quality.
- **Secondary**: `google/gemma-2-9b-it` (OpenRouter) — Fallback if rate-limited.
- **Failover**: `confmind-planner` (Local Gemma4 via Ollama) — Offline protector.

### State Synchronization (Deltas)
To avoid `INVALID_CONCURRENT_GRAPH_UPDATE` errors during parallel execution, the system uses:
- **Annotated Reducers**: `errors` (operator.add) and `metadata` (operator.ior) in `AgentState`.
- **Delta-based Returns**: Agents return ONLY the keys they modify. LangGraph automatically merges these fragments into the global state.

---

## 🤖 Agent Registry

### 1. `SponsorAgent`
- **Role**: Discovers and ranks potential event sponsors.
- **Tools**: Serper Search + ScrapeGraph-AI.
- **Logic**: Uses a deterministic 20-point scoring formula (Industry Relevance, Geography, Tier).
- **Output**: Ranked `sponsors` list + PDF sponsorship proposals in `metadata`.

### 2. `SpeakerAgent`
- **Role**: Identifies high-impact speakers and KOLs.
- **Tools**: Serper Search + LinkedIn Enrichment.
- **Logic**: Calculates an `influence_score` based on followers, connections, and posting frequency.
- **Output**: `speakers` list with profile data and influence metrics.

### 3. `VenueAgent`
- **Role**: Suggests locations based on capacity and budget.
- **Tools**: Serper Search + Scraper.
- **Output**: `venues` list including capacity, pricing estimates, and previous event history.

### 4. `ExhibitorAgent`
- **Role**: Maps out exhibition floor partners (Startups vs. Enterprise).
- **Tools**: SearchGraph.
- **Output**: `exhibitors` list clustered by industry tier.

### 5. `PricingAgent`
- **Role**: Mathematical model for ticket pricing.
- **Logic**: Uses local LLM to optimize Profit vs. Attendance based on target audience size.
- **Output**: `pricing` strategy (Tiered Early/General/VIP).

### 6. `CommunityGTMAgent`
- **Role**: Distribution and marketing.
- **Tools**: Community Search (Discord/Slack/Reddit).
- **Output**: `gtm_messages` customized for LinkedIn, Twitter, and Email.

### 7. `EventOpsAgent`
- **Role**: Detailed project management.
- **Output**: `schedule` — An hour-by-hour run-of-show including sessions, breaks, and networking.

### 8. `RevenueAgent`
- **Role**: Final financial auditing.
- **Logic**: Aggregates all costs vs. projected ticket and sponsor revenue.
- **Output**: `revenue` object containing Total Revenue, Total Costs, Profit, and ROI.

---

## 🛠️ Tooling & Resilience

- **Robust Scraper**: The `scraper_tool.py` includes a `_parse_json_result` helper that strips "Thinking" text or markdown fences from local LLM outputs, ensuring JSON parsing never fails.
- **PDF Stubbing**: `pdf_generator.py` detects missing system dependencies (GTK+) and provides a mock PDF fallback to prevent orchestration crashes on Windows.
- **Vector Memory**: `_read_memory` and `_write_memory` allow agents to learn from past planning sessions using a local ChromaDB instance.

---

## 🚀 Monitoring & Testing

- **Real-time Logs**: Agents use `self._log_info()` to pipe "Thinking" logs to the console.
- **Test Suite**: Run `test suryansh/main_test.py` to see the full graph execute end-to-end.
- **Observability**: Fully integrated with **LangSmith** via the `.env` configuration.
