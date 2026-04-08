"""
serper_tool.py — Google Search via Serper.dev API.

Serper wraps Google Search and returns structured JSON results.  This module
provides thin wrappers used by the Sponsor, Speaker, Exhibitor, Venue and
Community GTM agents to discover relevant entities from the web.

Environment variables
─────────────────────
SERPER_API_KEY   Required.  Get a free key at https://serper.dev

Public interface
────────────────
search_web(query, num_results)             -> list[SerperResult]
search_sponsors(category, geo, year)       -> list[SerperResult]
search_speakers(topic, region)             -> list[SerperResult]
search_venues(city, event_type)            -> list[SerperResult]
search_communities(topic)                  -> list[SerperResult]

Errors
──────
SerperAPIError   Raised on any non-200 HTTP response.

Usage example
─────────────
    from backend.tools.serper_tool import search_sponsors

    results = search_sponsors("AI", "Europe", year=2025)
    for r in results:
        print(r.title, r.url)
"""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

from backend.models.schemas import SerperResult

load_dotenv()

_SERPER_URL = "https://google.serper.dev/search"
_DEFAULT_NUM_RESULTS = 10


# ─────────────────────────────────────────────
# Custom exception
# ─────────────────────────────────────────────


class SerperAPIError(Exception):
    """Raised when the Serper API returns a non-200 status."""

    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"Serper API error {status_code}: {body}")
        self.status_code = status_code
        self.body = body


# ─────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────


def _get_api_key() -> str:
    """Fetch SERPER_API_KEY from environment, raise if missing."""
    key = os.getenv("SERPER_API_KEY", "")
    if not key:
        raise OSError("SERPER_API_KEY is not set. Add it to your .env file or export it.")
    return key


def _call_serper(query: str, num_results: int, api_key: str) -> dict:
    """Make the raw POST request to Serper and return the parsed JSON body."""
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": num_results}
    response = requests.post(_SERPER_URL, json=payload, headers=headers, timeout=15)
    if response.status_code != 200:
        raise SerperAPIError(response.status_code, response.text)
    return response.json()


def _parse_results(raw: dict) -> list[SerperResult]:
    """Convert raw Serper JSON into a list of SerperResult models.

    Serper returns results under 'organic'; each item has title, link, snippet.
    """
    organic = raw.get("organic", [])
    results: list[SerperResult] = []
    for i, item in enumerate(organic, start=1):
        results.append(
            SerperResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                position=i,
            )
        )
    return results


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────


def search_web(
    query: str,
    num_results: int = _DEFAULT_NUM_RESULTS,
    *,
    api_key: str | None = None,
) -> list[SerperResult]:
    """Generic Google search.

    Args:
        query:       The search query string.
        num_results: How many results to request (1-100, default 10).
        api_key:     Override SERPER_API_KEY env var (useful in tests).

    Returns:
        A list of SerperResult objects ordered by search rank.
    """
    key = api_key or _get_api_key()
    raw = _call_serper(query, num_results, key)
    return _parse_results(raw)


def search_sponsors(
    category: str,
    geo: str,
    year: int = 2025,
    num_results: int = _DEFAULT_NUM_RESULTS,
    *,
    api_key: str | None = None,
) -> list[SerperResult]:
    """Search for companies that sponsor events in a given category and region.

    Builds a query like: "AI conference sponsors Europe 2025"

    Args:
        category:    Event category (e.g. "AI", "Web3", "ClimateTech").
        geo:         Geography string (e.g. "Europe", "India", "USA").
        year:        Target year for sponsor recency (default 2025).
        num_results: Number of results to return.
        api_key:     Override for SERPER_API_KEY.
    """
    query = f"{category} conference sponsors {geo} {year}"
    return search_web(query, num_results, api_key=api_key)


def search_speakers(
    topic: str,
    region: str,
    num_results: int = _DEFAULT_NUM_RESULTS,
    *,
    api_key: str | None = None,
) -> list[SerperResult]:
    """Search for speakers who speak on a given topic in a region.

    Builds a query like: "AI conference speakers India 2025"
    """
    query = f"{topic} conference speakers {region} 2025"
    return search_web(query, num_results, api_key=api_key)


def search_venues(
    city: str,
    event_type: str,
    num_results: int = _DEFAULT_NUM_RESULTS,
    *,
    api_key: str | None = None,
) -> list[SerperResult]:
    """Search for event venues in a city for a given event type.

    Builds a query like: "conference venues Mumbai tech event"
    """
    query = f"conference venues {city} {event_type} event"
    return search_web(query, num_results, api_key=api_key)


def search_communities(
    topic: str,
    num_results: int = _DEFAULT_NUM_RESULTS,
    *,
    api_key: str | None = None,
) -> list[SerperResult]:
    """Search for online communities (Discord, Slack, Reddit) for a topic.

    Used by the Community GTM Agent to discover distribution channels.
    Builds a query like: "AI Discord server community join"
    """
    query = f"{topic} Discord server OR Slack community join"
    return search_web(query, num_results, api_key=api_key)
