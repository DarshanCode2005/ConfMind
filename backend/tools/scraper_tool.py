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
    base_url = os.getenv("OPENAI_BASE_URL", None)

    # ScrapeGraph uses the "openai/" prefix internally for its provider routing.
    # When a custom base_url is set (e.g. Nvidia NIM), we pass the bare model name
    # and set openai_api_base — ScrapeGraph's recognized key for custom endpoints.
    # Without base_url: keep the "openai/" prefix so ScrapeGraph routes correctly to OpenAI.
    raw_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not key:
        raise OSError("OPENAI_API_KEY is not set. Add it to your .env file or export it.")

    if base_url:
        # ScrapeGraph must receive a plain dict — it does not accept model instances.
        # Its provider detection works by reading the prefix from the model name:
        #   "openai/<xyz>" → uses openai provider, strips prefix, sends "<xyz>" to API.
        # For Nvidia: prefix with "openai/" so ScrapeGraph routes to its OpenAI provider,
        # which then strips it and sends the real model name (e.g. "meta/llama-3.3-70b-instruct")
        # as the model field in the HTTP request body — exactly what Nvidia expects.
        nvidia_model = raw_model[7:] if raw_model.startswith("openai/") else raw_model
        return {
            "model": f"openai/{nvidia_model}",  # e.g. openai/meta/llama-3.3-70b-instruct
            "api_key": key,
            "openai_api_base": base_url,
        }
    else:
        # Standard OpenAI — add "openai/" prefix if not already present
        model_name = raw_model if raw_model.startswith("openai/") else f"openai/{raw_model}"
        return {
            "model": model_name,
            "api_key": key,
        }


# ─────────────────────────────────────────────
# Wrapper classes
# ─────────────────────────────────────────────


def _crawl4ai_llm_config(api_key: str | None = None) -> Any:
    """Helper to convert environment vars to Crawl4AI LLMConfig."""
    import os

    from crawl4ai import LLMConfig

    key = api_key or os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "")
    raw_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if base_url:
        os.environ["OPENAI_API_BASE"] = base_url

    provider = raw_model if raw_model.startswith("openai/") else f"openai/{raw_model}"

    return LLMConfig(provider=provider, api_token=key)


class SmartScraperWrapper:
    """A pure-Crawl4AI alternative to ScrapeGraph-AI SmartScraperGraph.
    Uses AsyncWebCrawler and LLMExtractionStrategy for intelligent, robust scraping.
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
        """Scrape a URL and return extracted data as a raw dict."""
        import asyncio
        import json

        import requests
        from crawl4ai import (
            AsyncWebCrawler,
            BrowserConfig,
            CacheMode,
            CrawlerRunConfig,
            LLMExtractionStrategy,
        )

        async def _do_crawl():
            source_url = url
            try:
                # Bypass raw DNS Playwright issues by pre-fetching
                resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                if resp.ok and resp.text.strip():
                    source_url = f"raw://{resp.text}"
            except Exception:
                pass

            llm_strategy = LLMExtractionStrategy(
                llm_config=_crawl4ai_llm_config(api_key),
                instruction=f"{prompt}\nReturn ONLY a pure valid JSON dict. No lists.",
                extraction_type="block",
            )
            config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, extraction_strategy=llm_strategy)
            browser_config = BrowserConfig(headless=True)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                res = await crawler.arun(url=source_url, config=config)
                if not res.success:
                    raise ScraperError(f"Crawl4AI failed: {res.error_message}")

                content = res.extracted_content
                if not content:
                    return {}
                try:
                    data = json.loads(content)
                    return data
                except json.JSONDecodeError as e:
                    raise ScraperError(f"Crawl4AI JSON Error: {content} - {e}") from e

        try:
            data = asyncio.run(_do_crawl())
        except RuntimeError:
            loop = asyncio.get_event_loop()
            data = loop.run_until_complete(_do_crawl())

        if isinstance(data, list):
            if not data:
                return {}
            return data[0]
        return data

    def scrape_list(
        self,
        url: str,
        prompt: str,
        *,
        api_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Scrape a URL and return extracted data as a list of dicts (for calendars)."""
        import asyncio
        import json

        import requests
        from crawl4ai import (
            AsyncWebCrawler,
            BrowserConfig,
            CacheMode,
            CrawlerRunConfig,
            LLMExtractionStrategy,
        )

        async def _do_crawl_list():
            source_url = url
            try:
                resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                if resp.ok and resp.text.strip():
                    source_url = f"raw://{resp.text}"
            except Exception:
                pass

            llm_strategy = LLMExtractionStrategy(
                llm_config=_crawl4ai_llm_config(api_key),
                instruction=f"{prompt}\nReturn ONLY a pure valid JSON LIST of dicts (`[{{...}}]`).",
                extraction_type="block",
            )
            config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, extraction_strategy=llm_strategy)
            browser_config = BrowserConfig(headless=True)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                res = await crawler.arun(url=source_url, config=config)
                if not res.success:
                    raise ScraperError(f"Crawl4AI failed: {res.error_message}")

                content = res.extracted_content
                if not content:
                    return []
                try:
                    data = json.loads(content)
                    if isinstance(data, dict):
                        return [data]
                    return data
                except json.JSONDecodeError as e:
                    raise ScraperError(f"Crawl4AI JSON Error: {content} - {e}") from e

        try:
            return asyncio.run(_do_crawl_list())
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(_do_crawl_list())


class SearchGraphWrapper:
    """A SearchGraph equivalent using Crawl4AI and Serper."""

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
        """Run a search query and return a list of extracted records."""
        import asyncio
        import json

        import requests
        from crawl4ai import (
            AsyncWebCrawler,
            BrowserConfig,
            CacheMode,
            CrawlerRunConfig,
            LLMExtractionStrategy,
        )

        from backend.tools.serper_tool import search_web

        # 1. Search Google
        try:
            search_results = search_web(query, num_results=self._max_results)
        except Exception as e:
            raise ScraperError(f"Search failed: {e}") from e

        async def _do_search():
            all_records = []
            browser_config = BrowserConfig(headless=True)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                for res in search_results:
                    source_url = res.url
                    try:
                        resp = requests.get(
                            source_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
                        )
                        if resp.ok and resp.text.strip():
                            source_url = f"raw://{resp.text}"
                    except Exception:
                        pass

                    llm_strategy = LLMExtractionStrategy(
                        llm_config=_crawl4ai_llm_config(api_key),
                        instruction=f"{prompt}\nReturn ONLY a pure valid JSON LIST of dicts (`[{{...}}]`).",
                        extraction_type="block",
                    )
                    config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS, extraction_strategy=llm_strategy
                    )

                    crawl_res = await crawler.arun(url=source_url, config=config)
                    if crawl_res.success and crawl_res.extracted_content:
                        try:
                            parts = json.loads(crawl_res.extracted_content)
                            if isinstance(parts, list):
                                all_records.extend(parts)
                            elif isinstance(parts, dict):
                                all_records.append(parts)
                        except json.JSONDecodeError:
                            pass
            return all_records

        try:
            return asyncio.run(_do_search())
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(_do_search())


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
