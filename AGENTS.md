# AGENTS.md — ConfMind Coding Agent Rules

> Read this file **before writing any code** for this repository.
> These rules apply to every AI coding agent, Copilot suggestion, and human contributor.

---

## 1. Project at a Glance

**ConfMind** is a Python + Next.js multi-agent conference organizer.
- **Backend**: FastAPI + LangGraph + LangChain (Python 3.11+, in `backend/`)
- **Agents**: 8 specialized agents in `backend/agents/`, all inheriting `BaseAgent`
- **Shared state**: `AgentState` TypedDict in `backend/models/schemas.py` — the single source of truth flowing through LangGraph
- **Tool layer**: `backend/tools/` — fully built and tested; import from here, do not reimplement
- **Tests**: `pytest` in `tests/` — all external I/O must be mocked

---

## 2. Non-Negotiable Rules

### 2.1 Never Call External APIs in Tests
All tests must mock every external call (Serper, ScrapeGraph-AI, RapidAPI, OpenAI, WeasyPrint).
Use `unittest.mock.patch` targeting the import path inside the module under test, e.g.:

```python
@patch("backend.agents.sponsor_agent.search_sponsors_structured", return_value=[...])
```

### 2.2 Inherit BaseAgent — Always
Every new agent **must** subclass `BaseAgent` from `backend/agents/base_agent.py`.

```python
from backend.agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    name: str = "my_agent"          # unique; must match the LangGraph node name in orchestrator.py

    def _build_prompt(self) -> ChatPromptTemplate: ...
    def run(self, state: AgentState) -> AgentState: ...
```

### 2.3 Wrap `run()` in try/except
Never let an agent crash the whole pipeline. Always catch and log:

```python
def run(self, state: AgentState) -> AgentState:
    try:
        ...
    except Exception as exc:
        state = self._log_error(state, f"MyAgent failed: {exc}")
    return state
```

### 2.4 Import Tools — Don't Reimplement Them
The tool layer is complete. Use what's there:

| Need | Import from |
|---|---|
| Web scraping | `backend.tools.scraper_tool` |
| Google search | `backend.tools.serper_tool` |
| LinkedIn enrichment | `backend.tools.linkedin_tool` |
| PDF generation | `backend.tools.pdf_generator` |
| Schemas / state | `backend.models.schemas` |
| Vector memory | `backend.memory.vector_store` |

### 2.5 Write to `AgentState` — Never to Disk Directly
Agents communicate through `AgentState`. Store results in the correct field:

| Agent | Writes to |
|---|---|
| SponsorAgent | `state["sponsors"]`, `state["metadata"]` |
| SpeakerAgent | `state["speakers"]` |
| ExhibitorAgent | `state["exhibitors"]` |
| VenueAgent | `state["venues"]` |
| PricingAgent | `state["pricing"]` |
| CommunityGTMAgent | `state["communities"]`, `state["gtm_messages"]` |
| EventOpsAgent | `state["schedule"]` |
| RevenueAgent | `state["revenue"]` |

**Never** add new top-level keys to `AgentState` without updating `backend/models/schemas.py`.

### 2.6 One File Per Agent
Each agent lives in exactly one file under `backend/agents/`. Agent file names must match the node name:

```
backend/agents/my_agent.py   →   name = "my_agent"   →   node in orchestrator.py
```

---

## 3. Code Style

### 3.1 Linting (Ruff)
- Run `ruff check <file>` before every commit — 0 errors required.
- Run `ruff format <file>` to auto-format.
- Line length: **100 characters** (configured in `pyproject.toml`).
- No en-dashes (`–`) in docstrings or comments — use hyphen-minus (`-`). Ruff rule `RUF002/RUF003` will fail.
- No unused `# noqa` directives.

Quick commands (from activated venv):
```bash
ruff check backend/agents/          # check all agents
ruff format backend/agents/         # format all agents
```

### 3.2 Type Annotations
- **All** function signatures must have type annotations (parameters + return type).
- Use `from __future__ import annotations` at the top of every file.
- `pyright` type-checking is set to `"basic"` — don't suppress real type errors with `# type: ignore` unless you add a comment explaining why.

### 3.3 Docstrings
- Module-level docstring: what the module does, its public interface, env vars needed, and a usage example.
- Class-level docstring: agent role, sources used, output fields written.
- Method-level docstrings for all public methods (`run`, `_build_prompt`, private helpers).
- Use Google-style docstrings (Args / Returns / Raises).

### 3.4 Imports Order
Ruff/isort enforces this automatically. The expected order:

```python
from __future__ import annotations      # 1. futures

import os                               # 2. stdlib

from langchain_core.prompts import ...  # 3. third-party

from backend.models.schemas import ...  # 4. first-party (backend.*, scraping.*)

from .base_agent import BaseAgent       # 5. relative
```

---

## 4. Testing Rules

### 4.1 Test File Location and Name
```
backend/agents/sponsor_agent.py  →  tests/test_sponsor_agent.py
```

### 4.2 Minimum Test Coverage per Agent
Every agent test file must include at least:
- [ ] `run()` returns an `AgentState`-compatible dict with the expected key
- [ ] Output list is sorted by score (if applicable)
- [ ] Deduplication works (if merging from multiple sources)
- [ ] `state["errors"]` is populated when a tool raises
- [ ] Empty tool returns are handled gracefully (no crash, no error)

### 4.3 Shared Fixtures
Common fixtures live in `tests/conftest.py` — check there before defining new ones.
Available: `sample_sponsor`, `sample_speaker`, `sample_venue`, `sample_event`, `sample_exhibitor`, `sample_tier`, `sample_linkedin_profile`, `sample_serper_result`, `mock_serper_response`, `mock_search_graph_sponsors_list`, `mock_linkedin_api_response`, `sample_events_df`.

### 4.4 Run Tests
```bash
# Activate venv first:
source venv/bin/activate

pytest tests/test_<agent_name>.py -v    # single agent
pytest tests/ -v                        # all tests
```

---

## 5. Commit Convention

This repo uses **Conventional Commits** enforced by Husky + Commitlint.
Run `npm install` once after cloning to activate the hook.

### Format
```
type(scope): short description

Reason: explain WHY this change was made (not just what).
```

### Valid Types
| Type | When to use |
|---|---|
| `feat` | New feature or new agent file |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding or fixing tests |
| `refactor` | Code change with no behavior change |
| `style` | Formatting only |
| `chore` | Build, dependencies, CI |

### Scope Examples
`agents`, `tools`, `memory`, `models`, `frontend`, `data`, `orchestrator`, `docs`

### Good vs Bad
```bash
# Bad — describes WHAT, not WHY:
git commit -m "fix: update sponsor scoring"

# Good — describes WHY:
git commit -m "fix(agents): cap relevance_score at 10.0 to stay inside SponsorSchema bounds

Reason: normalising raw 0-20 score before storing prevents Pydantic
validation errors when the scraper returns a full-match Gold sponsor."
```

### Micro-commit Policy
Commit **after each logical unit of work**, not at end of day:
1. After creating an agent file → `feat(agents): implement <name>_agent`
2. After creating its test file → `test(agents): add unit tests for <name>_agent`
3. After adding docs → `docs(agents): document <name>_agent in README`

---

## 6. Branch Strategy

```
main        ← stable, always deployable; protected
feat/*      ← new agents / features (e.g. feat/speaker-agent)
fix/*       ← bug fixes
docs/*      ← documentation only
```

- **Never commit directly to `main`**.
- Open a PR from your feature branch; request review from P1 (lead).
- Branch names use kebab-case: `feat/sponsor-agent`, not `feat/SponsorAgent`.

---

## 7. Environment Variables

Required for the backend to run. Copy `.env.example` → `.env` and fill in:

| Variable | Used by | Required |
|---|---|---|
| `OPENAI_API_KEY` | All LLM agents + ScrapeGraph-AI | Yes |
| `SERPER_API_KEY` | `serper_tool.py` | Yes |
| `RAPIDAPI_KEY` | `linkedin_tool.py` | Yes (SpeakerAgent) |
| `PINECONE_API_KEY` | `vector_store.py` (prod) | Optional (ChromaDB is default) |
| `PINECONE_ENV` | `vector_store.py` (prod) | Optional |
| `DATABASE_URL` | `postgres_store.py` | Optional (Supabase) |
| `USE_PINECONE` | `vector_store.py` | Optional (`false` = ChromaDB) |

**Never** commit a `.env` file. It is gitignored.

---

## 8. What NOT to Do

| Don't | Do instead |
|---|---|
| Add new Pydantic schemas in agent files | Put schemas in `backend/models/schemas.py` |
| Call `requests` or `httpx` directly in an agent | Use the tool layer wrappers |
| Use `print()` for debugging | Use `self._log_error()` for errors; live without print in production |
| Hardcode API keys | Use `os.getenv()` with a clear error message |
| Write tests that hit real APIs | Mock all external I/O via `unittest.mock.patch` |
| Skip the `try/except` in `run()` | Always wrap the full body |
| Add a key to `AgentState` without updating `schemas.py` | Update `schemas.py` first, then use the key |
