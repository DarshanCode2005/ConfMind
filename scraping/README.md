# Scraping Utilities — Internal Documentation

This package implements the data extraction pipeline: from raw scraped HTML to clean `EventSchema` records stored as CSV/JSON.

---

## Pipeline Overview

```
Web page / Search results
        │
        ▼
SmartScraperGraph / SearchGraph   ← scrapegraph_runner.py
        │   (LLM-powered extraction)
        ▼
Raw dict (unvalidated, inconsistent types)
        │
        ▼
etl_pipeline.py                   ← normalize_event(), normalize_date() …
        │
        ▼
EventSchema (Pydantic v2, validated)
        │
        ▼
save_to_csv() / save_to_json()    → dataset/events_2025_2026.{csv,json}
```

---

## `prompts.py` — Extraction Prompt Constants

Each constant is the `prompt` string passed to ScrapeGraph-AI.  The LLM uses it to know exactly which JSON fields to extract.

| Constant | Used for |
|---|---|
| `EVENTBRITE_PROMPT` | `SmartScraperGraph` on Eventbrite event pages |
| `LUMA_PROMPT` | `SmartScraperGraph` on Luma event pages |
| `SESSIONIZE_PROMPT` | `SmartScraperGraph` on Sessionize CFP pages |
| `CVENT_PROMPT` | `SmartScraperGraph` on Cvent event listings |
| `EVENTLOCATIONS_PROMPT` | `SmartScraperGraph` on Eventlocations venue pages |
| `SPONSOR_SEARCH_PROMPT` | `SearchGraph` for sponsor discovery |
| `SPEAKER_SEARCH_PROMPT` | `SearchGraph` for speaker discovery |
| `EXHIBITOR_SEARCH_PROMPT` | `SearchGraph` for exhibitor discovery |
| `PROMPT_BY_SOURCE` | `dict` mapping source name → prompt (used by `scrapegraph_runner`) |

**When to edit**: If extraction quality is poor for a source, refine that source's prompt here — no agent code changes needed.

---

## `scrapegraph_runner.py` — High-Level Runners

Wraps the lower-level `SmartScraperWrapper` / `SearchGraphWrapper` from `backend/tools/scraper_tool.py` with:
- Automatic prompt selection via `PROMPT_BY_SOURCE`
- Retry logic (exponential back-off, `MAX_RETRIES = 3`)

### Functions

| Function | Args | Returns |
|---|---|---|
| `run_smart_scraper(url, source_name, *, api_key)` | url, source_name: str | `dict` |
| `run_search_graph(query, source_name, *, api_key, max_results)` | query, source_name: str | `list[dict]` |

**`source_name` for `run_smart_scraper`**: `"eventbrite"`, `"luma"`, `"sessionize"`, `"cvent"`, `"eventlocations"`

**`source_name` for `run_search_graph`**: `"sponsor"`, `"speaker"`, `"exhibitor"`

**Usage**:
```python
from scraping.scrapegraph_runner import run_smart_scraper, run_search_graph

raw = run_smart_scraper("https://eventbrite.com/e/ai-summit", "eventbrite")
sponsors = run_search_graph("AI conference sponsors Europe", "sponsor")
```

---

## `etl_pipeline.py` — Normalisation + I/O

### Normalisation Functions

| Function | Input | Output | Notes |
|---|---|---|---|
| `normalize_date(date_str)` | Any date string | ISO 8601 `"YYYY-MM-DD"` | Tries 8 common formats; passthrough on failure |
| `normalize_price(price_str)` | `"$1,500"`, `"Free"`, `"£200"` … | `float` (USD) | Conversion rates: GBP×1.27, EUR×1.08, INR×0.012 etc. |
| `normalize_country(raw)` | `"India"`, `"UK"`, `"de"` … | ISO alpha-2 uppercase | Checks alias map first, then 2-char passthrough |
| `normalize_event(raw)` | Raw scraped `dict` | `EventSchema` | Calls all three normalizers above |

### Deduplication

```python
deduplicate(records, key_fields=["event_name", "city"])
```
Keeps the **first** occurrence of each unique `(event_name, city)` tuple.

### I/O Helpers

| Function | Behaviour |
|---|---|
| `save_to_csv(records, path)` | List-valued fields serialised as pipe-separated strings |
| `save_to_json(records, path)` | Pretty-printed JSON with `indent=2` |

Both automatically create any missing parent directories.

**Known limitation**: `normalize_price` uses hardcoded approximate conversion rates — suitable for the MVP dataset but should be replaced with a live FX API for production.
