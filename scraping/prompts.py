"""
prompts.py — Natural-language extraction prompts for each scraping source.

Each constant is passed as the `prompt` argument to SmartScraperGraph or
SearchGraph.  The LLM uses the prompt to know which fields to extract and
in what format.

Naming convention:
  <SOURCE>_PROMPT    — for SmartScraperGraph (single URL)
  <ENTITY>_SEARCH_PROMPT  — for SearchGraph (multi-source search)
"""

# ─────────────────────────────────────────────
# Single-URL extraction prompts (SmartScraperGraph)
# ─────────────────────────────────────────────

EVENTBRITE_PROMPT = (
    "Extract from this Eventbrite page: event_name, date (ISO 8601 YYYY-MM-DD), "
    "city, country (ISO 3166-1 alpha-2), category, theme, "
    "sponsors (list of company names), speakers (list of speaker names), "
    "ticket_price_early (number in USD), ticket_price_general (number in USD), "
    "ticket_price_vip (number in USD), estimated_attendance (integer), "
    "venue_name, venue_capacity (integer), source_url."
)

LUMA_PROMPT = (
    "Extract from this Luma event page: event_name, date (ISO 8601 YYYY-MM-DD), "
    "city, country (ISO 3166-1 alpha-2), category, theme, "
    "sponsors (list of names), speakers (list of names), "
    "ticket_price_general (number in USD, 0 if free), "
    "estimated_attendance (integer), venue_name, source_url."
)

SESSIONIZE_PROMPT = (
    "Extract from this Sessionize call-for-papers page: event_name, date (ISO 8601), "
    "city, country (ISO 3166-1 alpha-2), category, "
    "speakers (list of speaker names with bio snippets as dicts {name, bio, topic}), "
    "source_url."
)

CVENT_PROMPT = (
    "Extract from this Cvent event listing: event_name, date (ISO 8601 YYYY-MM-DD), "
    "city, country (ISO 3166-1 alpha-2), category, theme, "
    "sponsors (list of company names), estimated_attendance (integer), "
    "venue_name, venue_capacity (integer), source_url."
)

EVENTLOCATIONS_PROMPT = (
    "Extract from this venue listing page: name (venue name), city, country "
    "(ISO 3166-1 alpha-2), capacity (integer), "
    "price_range (string, e.g. '$5,000-$15,000/day'), "
    "past_events (list of event names held here), source_url."
)

# ─────────────────────────────────────────────
# Multi-source search prompts (SearchGraph)
# ─────────────────────────────────────────────

SPONSOR_SEARCH_PROMPT = (
    "For each result, extract: name (company name), website (URL), industry, "
    "geo (country or region), tier (Gold/Silver/Bronze/General, default General). "
    "Return a list of objects with these fields."
)

SPEAKER_SEARCH_PROMPT = (
    "For each result, extract: name (speaker full name), bio (short biography), "
    "linkedin_url (if visible), topic (keynote or talk topic), region (country or city). "
    "Return a list of objects with these fields."
)

EXHIBITOR_SEARCH_PROMPT = (
    "For each result, extract: name (company or exhibitor name), "
    "cluster (startup/enterprise/tools/individual), "
    "website (URL if available). "
    "Return a list of objects with these fields."
)

GENERIC_EVENTS_PROMPT = (
    "This is a conference or event listing page. "
    "Extract all events visible on the page as a list. For each event extract: "
    "event_name (string), date (any date string you can find), city (string), "
    "country (string), category (e.g. Tourism, AI, Tech, Business), "
    "theme (short description or subtitle), estimated_attendance (integer if shown, else 0), "
    "venue_name (string if shown), source_url (the full URL of this page). "
    "Return a list of event objects with exactly these field names."
)

# Map source name string -> SmartScraperGraph prompt constant.
# Used by scrapegraph_runner.run_smart_scraper(url, source_name).
PROMPT_BY_SOURCE: dict[str, str] = {
    "eventbrite": EVENTBRITE_PROMPT,
    "luma": LUMA_PROMPT,
    "sessionize": SESSIONIZE_PROMPT,
    "cvent": CVENT_PROMPT,
    "eventlocations": EVENTLOCATIONS_PROMPT,
    "generic": GENERIC_EVENTS_PROMPT,  # for any public events listing page
}
