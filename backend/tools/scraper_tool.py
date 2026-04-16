"""
scraper_tool.py — ScrapeGraph-AI wrappers for structured web extraction with multi-model fallback.
"""

from __future__ import annotations

import os
import json
import re
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

# ── Extraction Prompts ────────────────────────
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


class ScraperError(Exception):
    """Raised when ScrapeGraph-AI returns empty or invalid data."""


def _get_llm_candidates() -> list[dict[str, Any]]:
    """Return a list of LLM configurations in order of preference."""
    from backend.config import (
        PRIMARY_MODEL, SECONDARY_MODEL, LOCAL_MODEL,
        MAX_TOKENS, OPENROUTER_BASE_URL
    )
    
    or_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("openrouter_key")
    candidates = []

    # 1. OpenRouter Primary
    if or_key:
        candidates.append({
            "model": f"openai/{PRIMARY_MODEL}",
            "api_key": or_key,
            "base_url": OPENROUTER_BASE_URL,
            "max_tokens": MAX_TOKENS,
        })
        # 2. OpenRouter Secondary
        candidates.append({
            "model": f"openai/{SECONDARY_MODEL}",
            "api_key": or_key,
            "base_url": OPENROUTER_BASE_URL,
            "max_tokens": MAX_TOKENS,
        })

    # 3. Local Ollama (Always available if Ollama is running)
    candidates.append({
        "model": f"ollama/{LOCAL_MODEL}",
        "base_url": "http://localhost:11434",
    })

    return candidates


def _parse_json_result(result: Any) -> Any:
    """Extract JSON from potentially chatty LLM output (e.g. local Gemma4)."""
    if isinstance(result, (dict, list)):
        return result
    if isinstance(result, str):
        text = re.sub(r"```(?:json)?\s*", "", result)
        text = re.sub(r"```", "", text)
        text = text.strip()
        for start_char in ["[", "{"]:
            idx = text.find(start_char)
            if idx != -1:
                try:
                    return json.loads(text[idx:])
                except json.JSONDecodeError:
                    pass
    return result


class SmartScraperWrapper:
    def __init__(self, llm_config: dict[str, Any] | None = None) -> None:
        self._llm_config = llm_config

    def scrape(self, url: str, prompt: str, *, api_key: str | None = None) -> dict[str, Any]:
        from scrapegraphai.graphs import SmartScraperGraph  # type: ignore[import-untyped]

        configs = [self._llm_config] if self._llm_config else _get_llm_candidates()
        last_error = None

        for cfg in configs:
            try:
                print(f"  [SCRAPER] Trying {cfg['model']} for URL: {url}")
                # Add strict directive for chatty models
                prompt_suffix = ""
                if "ollama" in cfg['model'] or "gemma" in cfg['model']:
                    prompt_suffix = " IMPORTANT: Output ONLY valid JSON. No text before or after."

                graph = SmartScraperGraph(prompt=f"{prompt}{prompt_suffix}", source=url, config={"llm": cfg})
                raw_result = graph.run()
                result = _parse_json_result(raw_result)

                if result:
                    return dict(result)
            except Exception as e:
                print(f"  [SCRAPER][WARN] Model {cfg['model']} failed: {e}")
                last_error = e

        raise ScraperError(f"All models failed for URL {url}. Last error: {last_error}")


class SearchGraphWrapper:
    def __init__(self, llm_config: dict[str, Any] | None = None, max_results: int = 5) -> None:
        self._llm_config = llm_config
        self._max_results = max_results

    def search(self, query: str, prompt: str, *, api_key: str | None = None) -> list[dict[str, Any]]:
        from scrapegraphai.graphs import SearchGraph  # type: ignore[import-untyped]

        configs = [self._llm_config] if self._llm_config else _get_llm_candidates()
        last_error = None

        for cfg in configs:
            try:
                print(f"  [SCRAPER] Trying {cfg['model']} for Search: {query}")
                prompt_suffix = ""
                if "ollama" in cfg['model'] or "gemma" in cfg['model']:
                    prompt_suffix = " IMPORTANT: Output ONLY valid JSON. No text before or after."

                graph = SearchGraph(
                    prompt=f"{query}. {prompt}{prompt_suffix}",
                    config={"llm": cfg, "max_results": self._max_results},
                )
                raw_result = graph.run()
                result = _parse_json_result(raw_result)

                if result:
                    if isinstance(result, list):
                        return [item for item in result if isinstance(item, dict)]
                    if hasattr(result, "values"):
                        for v in result.values():
                            if isinstance(v, list):
                                return [item for item in v if isinstance(item, dict)]
                    return [dict(result)]
            except Exception as e:
                print(f"  [SCRAPER][WARN] Model {cfg['model']} search failed: {e}")
                last_error = e

        raise ScraperError(f"All models failed for query {query!r}. Last error: {last_error}")


# ── Convenience functions ─────────────────────

def scrape_event_page(url: str, *, api_key: str | None = None) -> EventSchema:
    wrapper = SmartScraperWrapper()
    raw = wrapper.scrape(url, _EVENT_PAGE_PROMPT, api_key=api_key)
    raw.setdefault("source_url", url)
    return EventSchema(**{k: v for k, v in raw.items() if k in EventSchema.model_fields})

def scrape_venue_page(url: str, *, api_key: str | None = None) -> VenueSchema:
    wrapper = SmartScraperWrapper()
    raw = wrapper.scrape(url, _VENUE_PAGE_PROMPT, api_key=api_key)
    raw.setdefault("source_url", url)
    raw.setdefault("name", raw.pop("venue_name", "Unknown"))
    return VenueSchema(**{k: v for k, v in raw.items() if k in VenueSchema.model_fields})

def search_sponsors_structured(category: str, geo: str, *, api_key: str | None = None, max_results: int = 5) -> list[SponsorSchema]:
    query = f"{category} conference sponsors {geo} 2025"
    wrapper = SearchGraphWrapper(max_results=max_results)
    raw_list = wrapper.search(query, SPONSOR_SEARCH_PROMPT, api_key=api_key)
    return [SponsorSchema(**{k: v for k, v in item.items() if k in SponsorSchema.model_fields}) for item in raw_list if isinstance(item, dict)]

def search_speakers_structured(topic: str, region: str, *, api_key: str | None = None, max_results: int = 5) -> list[SpeakerSchema]:
    query = f"{topic} conference speakers {region} 2025"
    wrapper = SearchGraphWrapper(max_results=max_results)
    raw_list = wrapper.search(query, SPEAKER_SEARCH_PROMPT, api_key=api_key)
    return [SpeakerSchema(**{k: v for k, v in item.items() if k in SpeakerSchema.model_fields}) for item in raw_list if isinstance(item, dict)]

def search_exhibitors_structured(category: str, *, api_key: str | None = None, max_results: int = 5) -> list[ExhibitorSchema]:
    query = f"exhibitors at {category} conference 2025"
    wrapper = SearchGraphWrapper(max_results=max_results)
    raw_list = wrapper.search(query, EXHIBITOR_SEARCH_PROMPT, api_key=api_key)
    return [ExhibitorSchema(**{k: v for k, v in item.items() if k in ExhibitorSchema.model_fields}) for item in raw_list if isinstance(item, dict)]
