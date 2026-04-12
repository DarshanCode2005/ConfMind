"""
scrapegraph_runner.py — High-level runners that combine prompts + wrappers.

Provides retry logic and source-aware prompt selection on top of the lower-level
SmartScraperWrapper and SearchGraphWrapper classes.

Public interface
────────────────
run_smart_scraper(url, source_name)   -> dict
run_search_graph(query, source_name)  -> list[dict]

Both functions retry up to MAX_RETRIES times with exponential back-off.
"""

from __future__ import annotations

import time
from typing import Any

from backend.tools.scraper_tool import ScraperError, SearchGraphWrapper, SmartScraperWrapper
from scraping.prompts import PROMPT_BY_SOURCE, SPONSOR_SEARCH_PROMPT

MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds


def _with_retry(fn, *args, **kwargs) -> Any:
    """Call fn(*args, **kwargs) up to MAX_RETRIES times with exponential back-off."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except (ScraperError, Exception) as exc:
            last_exc = exc
            wait = _BACKOFF_BASE**attempt
            time.sleep(wait)
    raise last_exc or RuntimeError("Unknown error in _with_retry")


def run_smart_scraper(
    url: str,
    source_name: str,
    *,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Scrape a single URL using the prompt registered for source_name.

    Args:
        url:         Full URL to scrape.
        source_name: One of the keys in prompts.PROMPT_BY_SOURCE
                     ("eventbrite", "luma", "sessionize", "cvent", "eventlocations").
        api_key:     Override OPENAI_API_KEY.

    Returns:
        Raw dict from SmartScraperGraph.

    Raises:
        KeyError:    If source_name is not in PROMPT_BY_SOURCE.
        ScraperError: If all retries fail.
    """
    if source_name not in PROMPT_BY_SOURCE:
        raise KeyError(
            f"Unknown source {source_name!r}. Valid sources: {list(PROMPT_BY_SOURCE.keys())}"
        )
    prompt = PROMPT_BY_SOURCE[source_name]
    wrapper = SmartScraperWrapper()
    return _with_retry(wrapper.scrape, url, prompt, api_key=api_key)


def run_smart_scraper_list(
    url: str,
    source_name: str,
    *,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Scrape a URL that contains multiple entities (like a calendar).
    Uses the prompt registered for source_name.

    Args:
        url:         Full URL to scrape.
        source_name: One of the keys in prompts.PROMPT_BY_SOURCE.
        api_key:     Override OPENAI_API_KEY.

    Returns:
        List of raw dicts from SmartScraperWrapper.
    """
    if source_name not in PROMPT_BY_SOURCE:
        raise KeyError(
            f"Unknown source {source_name!r}. Valid sources: {list(PROMPT_BY_SOURCE.keys())}"
        )
    prompt = PROMPT_BY_SOURCE[source_name]
    wrapper = SmartScraperWrapper()
    return _with_retry(wrapper.scrape_list, url, prompt, api_key=api_key)


def run_search_graph(
    query: str,
    source_name: str = "sponsor",
    *,
    api_key: str | None = None,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Run a SearchGraph query using the prompt for a named entity type.

    Args:
        query:       The search query string.
        source_name: Entity type that selects the extraction prompt.
                     Use "sponsor", "speaker", or "exhibitor".
        api_key:     Override OPENAI_API_KEY.
        max_results: How many search results to scrape.

    Returns:
        List of raw dicts from SearchGraph.

    Raises:
        ScraperError: If all retries fail.
    """
    from scraping.prompts import EXHIBITOR_SEARCH_PROMPT, SPEAKER_SEARCH_PROMPT

    _search_prompts: dict[str, str] = {
        "sponsor": SPONSOR_SEARCH_PROMPT,
        "speaker": SPEAKER_SEARCH_PROMPT,
        "exhibitor": EXHIBITOR_SEARCH_PROMPT,
    }
    prompt = _search_prompts.get(source_name, SPONSOR_SEARCH_PROMPT)
    wrapper = SearchGraphWrapper(max_results=max_results)
    return _with_retry(wrapper.search, query, prompt, api_key=api_key)
