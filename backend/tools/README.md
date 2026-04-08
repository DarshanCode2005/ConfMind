# Tools — Internal Documentation

Quick reference for every module in `backend/tools/`.  Read this before wiring agents.

---

## `serper_tool.py` — Google Search

**Used by**: Sponsor Agent, Speaker Agent, Exhibitor Agent, Community GTM Agent, Venue Agent

### Public API

| Function | Args | Returns | Notes |
|---|---|---|---|
| `search_web(query, num_results, *, api_key)` | query: str | `list[SerperResult]` | Raw Google search |
| `search_sponsors(category, geo, year, ...)` | category, geo: str | `list[SerperResult]` | Query: `"{cat} conference sponsors {geo} {year}"` |
| `search_speakers(topic, region, ...)` | topic, region: str | `list[SerperResult]` | Query: `"{topic} conference speakers {region} 2025"` |
| `search_venues(city, event_type, ...)` | city, event_type: str | `list[SerperResult]` | Query: `"conference venues {city} {event_type} event"` |
| `search_communities(topic, ...)` | topic: str | `list[SerperResult]` | Query includes "Discord server OR Slack community join" |

**Env var**: `SERPER_API_KEY` (required)

**Errors**: `SerperAPIError(status_code, body)` on non-200 responses.

**Usage**:
```python
from backend.tools.serper_tool import search_sponsors
results = search_sponsors("AI", "Europe", api_key="sk-...")
for r in results:
    print(r.title, r.url)
```

---

## `scraper_tool.py` — ScrapeGraph-AI Wrappers

**Used by**: All scraping-dependent agents (Sponsor, Speaker, Exhibitor, Venue)

### Classes

**`SmartScraperWrapper`** — Single-URL structured extraction

| Method | Description |
|---|---|
| `scrape(url, prompt, *, api_key)` | Returns raw dict from SmartScraperGraph |

**`SearchGraphWrapper`** — Multi-source search + scrape

| Method | Description |
|---|---|
| `search(query, prompt, *, api_key)` | Returns `list[dict]` from SearchGraph |

### Convenience Functions

| Function | Returns |
|---|---|
| `scrape_event_page(url)` | `EventSchema` |
| `scrape_venue_page(url)` | `VenueSchema` |
| `search_sponsors_structured(category, geo)` | `list[SponsorSchema]` |
| `search_speakers_structured(topic, region)` | `list[SpeakerSchema]` |
| `search_exhibitors_structured(category)` | `list[ExhibitorSchema]` |

**Env var**: `OPENAI_API_KEY` (default LLM; override via `llm_config` dict)

**Errors**: `ScraperError` on empty graph results.

**Design note**: ScrapeGraph-AI is imported lazily inside each method to keep test startup fast when the class is mocked.

**Usage**:
```python
from backend.tools.scraper_tool import scrape_event_page
event = scrape_event_page("https://eventbrite.com/e/ai-summit-2025")
print(event.event_name, event.estimated_attendance)
```

---

## `linkedin_tool.py` — LinkedIn Enrichment

**Used by**: Speaker Agent

### Public API

| Function | Args | Returns |
|---|---|---|
| `get_profile(linkedin_url, *, api_key)` | URL str | `LinkedInProfile` |
| `calculate_influence_score(profile)` | `LinkedInProfile` | `float` (0.0-10.0) |
| `enrich_speakers(speakers, *, api_key)` | `list[SpeakerSchema]` | `list[SpeakerSchema]` |

**Env var**: `RAPIDAPI_KEY` (required)

**Retry**: 3 attempts with exponential back-off on HTTP 429.

**Errors**:
- `LinkedInRateLimitError` — exhausted 3 retries on 429
- `LinkedInAPIError` — other HTTP errors

**Influence score formula** (deterministic, no LLM):
```
followers_pts  = log10(followers + 1) / log10(100_001) * 6.0   (max 6 pts)
posts_pts      = min(posts, 10) / 10 * 2.0                      (max 2 pts)
connections_pts = min(connections, 500) / 500 * 2.0             (max 2 pts)
score = followers_pts + posts_pts + connections_pts              (max 10)
```

**Usage**:
```python
from backend.tools.linkedin_tool import enrich_speakers
enriched = enrich_speakers(speaker_list, api_key="rapidapi-key")
```

---

## `pdf_generator.py` — Sponsorship Proposal PDF

**Used by**: Sponsor Agent (proposal generation step)

### Public API

| Function | Args | Returns |
|---|---|---|
| `render_proposal(sponsor, event_meta)` | `SponsorSchema`, `dict` | `bytes` (PDF) |
| `save_proposal(sponsor, event_meta, output_path)` | — | `str` (absolute path) |

**Template**: `backend/templates/sponsorship_proposal.html` — Jinja2 HTML → WeasyPrint PDF

**`event_meta` dict keys**:
| Key | Type | Notes |
|---|---|---|
| `event_name` | str | required |
| `city` | str | required |
| `date` | str | ISO 8601 preferred |
| `country` | str | optional |
| `category` | str | optional |
| `audience_size` | str | optional |
| `contact_email` | str | defaults to `partnerships@confmind.ai` |

**Tier-specific content**: Gold → keynote slot; Silver → panel; Bronze → table-top; General → basic.

**Usage**:
```python
pdf_bytes = render_proposal(sponsor, {"event_name": "AI Summit 2025", "city": "Berlin", "date": "2025-09-15"})
```
