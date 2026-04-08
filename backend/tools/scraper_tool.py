"""
scraper_tool.py — ScrapeGraph-AI wrappers for structured web extraction.

ScrapeGraph-AI uses an LLM to extract structured JSON from web pages without
brittle CSS selectors.  This module wraps two of its graph types:

  SmartScraperGraph   Single-URL extraction → structured dict
  SearchGraph         Multi-source search + scrape → list[dict]

Every wrapper validates its output against Pydantic schemas from
backend.models.schemas, giving agents clean, typed objects.

Environment variables
─────────────────────
OPENAI_API_KEY   Required (default LLM backend for ScrapeGraph-AI).
                 Swap to Gemini etc. by passing a custom llm_config.

Public interface
────────────────
SmartScraperWrapper.scrape(url, prompt, schema_cls) -> dict
SearchGraphWrapper.search(query, prompt, schema_cls) -> list[dict]

Convenience functions (preferred by agents):
  scrape_event_page(url)                 -> EventSchema
  scrape_venue_page(url)                 -> VenueSchema
  search_sponsors_structured(cat, geo)   -> list[SponsorSchema]
  search_speakers_structured(topic, reg) -> list[SpeakerSchema]
  search_exhibitors_structured(category) -> list[ExhibitorSchema]

Errors
──────
ScraperError   Raised when ScrapeGraph-AI fails or returns no data.

Usage example
─────────────
    from backend.tools.scraper_tool import scrape_event_page

    event = scrape_event_page("https://events.example.com/ai-summit-2025")
    print(event.event_name, event.estimated_attendance)
"""

from __future__ import annotations

import os
from typing import Any, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel

from backend.models.schemas import (
    EventSchema,
    ExhibitorSchema,
    SpeakerSchema,
    SponsorSchema,
    VenueSchema,
)
from scraping.prompts import (
    EXHIBITOR_SEARCH_PROMPT,
    SPEAKER_SEARCH_PROMPT,
    SPONSOR_SEARCH_PROMPT,
)

load_dotenv()

T = TypeVar("T", bound=BaseModel)

# ─────────────────────────────────────────────
# Default prompt used when scraping event pages
# ─────────────────────────────────────────────

_EVENT_PAGE_PROMPT = (
    "Extract event details: event_name, date (ISO 8601), city, country, category, theme, "
    "list of sponsor names (sponsors), list of speaker names (speakers), "
    "list of exhibitor names (exhibitors), ticket_price_early (number), "
    "ticket_price_general (number), ticket_price_vip (number), "
    "estimated_attendance (integer), venue_name, venue_capacity (integer), source_url."
)

_VENUE_PAGE_PROMPT = (
    "Extract venue details: name, city, country, capacity (integer), "
    "price_range (string like '$5,000-$15,000/day'), "
    "list of past_events (event names), source_url."
)


# ─────────────────────────────────────────────
# Custom exception
# ─────────────────────────────────────────────


class ScraperError(Exception):
    """Raised when ScrapeGraph-AI returns empty or invalid data."""


# ─────────────────────────────────────────────
# Private helper: build LLM config dict
# ─────────────────────────────────────────────


def _default_llm_config(api_key: str | None = None) -> dict[str, Any]:
    """Build a ScrapeGraph-AI llm_config that targets GPT-4o-mini.

    GPT-4o-mini is used (not GPT-4o) to keep scraping costs low during
    development and hackathon testing.
    """
    key = api_key or os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise OSError("OPENAI_API_KEY is not set. Add it to your .env file or export it.")
    return {
        "model": "openai/gpt-4o-mini",
        "api_key": key,
    }


# ─────────────────────────────────────────────
# Wrapper classes
# ─────────────────────────────────────────────


class SmartScraperWrapper:
    """Wraps ScrapeGraph-AI SmartScraperGraph for single-URL extraction.

    SmartScraperGraph fetches a URL and uses an LLM to extract structured
    data matching the given prompt, with no need for CSS selectors.

    Args:
        llm_config: Override the default LLM config (model + api_key dict).
                    If None, uses GPT-4o-mini via OPENAI_API_KEY.
    """

    def __init__(self, llm_config: dict[str, Any] | None = None) -> None:
        self._llm_config = llm_config

    def scrape(
        self,
        url: str,
        prompt: str,
        *,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Scrape a URL and return extracted data as a raw dict.

        Args:
            url:     The page URL to scrape.
            prompt:  Natural-language instruction describing the fields to extract.
            api_key: Override OPENAI_API_KEY for this call.

        Returns:
            A dict whose keys match the fields described in the prompt.

        Raises:
            ScraperError: If ScrapeGraph-AI returns None or an empty dict.
        """
        # Import here to avoid slow startup when running tests that mock this class
        from scrapegraphai.graphs import SmartScraperGraph  # type: ignore[import-untyped]

        cfg = self._llm_config or _default_llm_config(api_key)
        graph = SmartScraperGraph(prompt=prompt, source=url, config={"llm": cfg})
        result: Any = graph.run()
        if not result:
            raise ScraperError(f"SmartScraperGraph returned empty result for URL: {url}")
        return dict(result)


class SearchGraphWrapper:
    """Wraps ScrapeGraph-AI SearchGraph for multi-source search + scrape.

    SearchGraph runs a web search query, visits the top results, and
    aggregates structured data from all pages in one LLM pass.

    Args:
        llm_config:    Override the default LLM config.
        max_results:   How many search results to scrape (default 5).
    """

    def __init__(
        self,
        llm_config: dict[str, Any] | None = None,
        max_results: int = 5,
    ) -> None:
        self._llm_config = llm_config
        self._max_results = max_results

    def search(
        self,
        query: str,
        prompt: str,
        *,
        api_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a search query and return a list of extracted records.

        Args:
            query:   The Google-style search query (no special syntax required).
            prompt:  What fields to extract from each result page.
            api_key: Override OPENAI_API_KEY for this call.

        Returns:
            A list of dicts; each dict represents one extracted entity.

        Raises:
            ScraperError: If SearchGraph returns no results.
        """
        from scrapegraphai.graphs import SearchGraph  # type: ignore[import-untyped]

        cfg = self._llm_config or _default_llm_config(api_key)
        graph = SearchGraph(
            prompt=f"{query}. {prompt}",
            config={"llm": cfg, "max_results": self._max_results},
        )
        result: Any = graph.run()
        if not result:
            raise ScraperError(f"SearchGraph returned empty result for query: {query!r}")
        # SearchGraph returns either a list or a dict with a list inside
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        # Some versions nest under a key
        if hasattr(result, "values"):
            for v in result.values():
                if isinstance(v, list):
                    return [item for item in v if isinstance(item, dict)]
        return [dict(result)]


# ─────────────────────────────────────────────
# Convenience functions
# ─────────────────────────────────────────────


def scrape_event_page(url: str, *, api_key: str | None = None) -> EventSchema:
    """Scrape a single event page (Eventbrite, Luma, etc.) → EventSchema.

    Uses the built-in event extraction prompt.
    """
    wrapper = SmartScraperWrapper()
    raw = wrapper.scrape(url, _EVENT_PAGE_PROMPT, api_key=api_key)
    # Provide source_url if not extracted
    raw.setdefault("source_url", url)
    return EventSchema(**{k: v for k, v in raw.items() if k in EventSchema.model_fields})


def scrape_venue_page(url: str, *, api_key: str | None = None) -> VenueSchema:
    """Scrape a single venue page (Cvent, Eventlocations) → VenueSchema."""
    wrapper = SmartScraperWrapper()
    raw = wrapper.scrape(url, _VENUE_PAGE_PROMPT, api_key=api_key)
    raw.setdefault("source_url", url)
    raw.setdefault("name", raw.pop("venue_name", "Unknown"))
    raw.setdefault("city", "")
    return VenueSchema(**{k: v for k, v in raw.items() if k in VenueSchema.model_fields})


def search_sponsors_structured(
    category: str,
    geo: str,
    *,
    api_key: str | None = None,
    max_results: int = 5,
) -> list[SponsorSchema]:
    """Search for sponsors via SearchGraph and return validated SponsorSchema objects.

    Args:
        category:    Event category (e.g. "AI", "Web3").
        geo:         Geography (e.g. "Europe", "India").
        api_key:     Override OPENAI_API_KEY.
        max_results: Number of search hits to scrape.
    """
    query = f"{category} conference sponsors {geo} 2025"
    wrapper = SearchGraphWrapper(max_results=max_results)
    raw_list = wrapper.search(query, SPONSOR_SEARCH_PROMPT, api_key=api_key)
    results: list[SponsorSchema] = []
    for item in raw_list:
        try:
            results.append(
                SponsorSchema(**{k: v for k, v in item.items() if k in SponsorSchema.model_fields})
            )
        except Exception:
            continue  # skip malformed records silently
    return results


def search_speakers_structured(
    topic: str,
    region: str,
    *,
    api_key: str | None = None,
    max_results: int = 5,
) -> list[SpeakerSchema]:
    """Search for speakers via SearchGraph and return validated SpeakerSchema objects."""
    query = f"{topic} conference speakers {region} 2025"
    wrapper = SearchGraphWrapper(max_results=max_results)
    raw_list = wrapper.search(query, SPEAKER_SEARCH_PROMPT, api_key=api_key)
    results: list[SpeakerSchema] = []
    for item in raw_list:
        try:
            results.append(
                SpeakerSchema(**{k: v for k, v in item.items() if k in SpeakerSchema.model_fields})
            )
        except Exception:
            continue
    return results


def search_exhibitors_structured(
    category: str,
    *,
    api_key: str | None = None,
    max_results: int = 5,
) -> list[ExhibitorSchema]:
    """Search for exhibitors via SearchGraph and return validated ExhibitorSchema objects."""
    query = f"exhibitors at {category} conference 2025"
    wrapper = SearchGraphWrapper(max_results=max_results)
    raw_list = wrapper.search(query, EXHIBITOR_SEARCH_PROMPT, api_key=api_key)
    results: list[ExhibitorSchema] = []
    for item in raw_list:
        try:
            results.append(
                ExhibitorSchema(
                    **{k: v for k, v in item.items() if k in ExhibitorSchema.model_fields}
                )
            )
        except Exception:
            continue
    return results
