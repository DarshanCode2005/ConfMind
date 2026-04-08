"""
test_scraper_tool.py — Unit tests for backend/tools/scraper_tool.py.

ScrapeGraph-AI is fully mocked; no real OpenAI API calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.models.schemas import EventSchema, ExhibitorSchema, SpeakerSchema, SponsorSchema
from backend.tools.scraper_tool import (
    ScraperError,
    SearchGraphWrapper,
    SmartScraperWrapper,
    scrape_event_page,
    scrape_venue_page,
    search_exhibitors_structured,
    search_speakers_structured,
    search_sponsors_structured,
)

# ─────────────────────────────────────────────
# SmartScraperWrapper
# ─────────────────────────────────────────────


def test_smart_scraper_wrapper_returns_dict(mock_smart_scraper_event_dict: dict) -> None:
    """SmartScraperWrapper.scrape should return the graph's result dict."""
    mock_graph = MagicMock()
    mock_graph.run.return_value = mock_smart_scraper_event_dict

    with patch("backend.tools.scraper_tool.SmartScraperWrapper.scrape") as mock_scrape:
        mock_scrape.return_value = mock_smart_scraper_event_dict
        wrapper = SmartScraperWrapper()
        result = wrapper.scrape("https://example.com", "Extract event details", api_key="fake")

    assert isinstance(result, dict)
    assert result["event_name"] == "AI Summit 2025"


def test_smart_scraper_wrapper_raises_on_empty_result() -> None:
    """SmartScraperWrapper.scrape should raise ScraperError when graph returns empty."""
    with patch("backend.tools.scraper_tool.SmartScraperWrapper.scrape") as mock_scrape:
        mock_scrape.side_effect = ScraperError("Empty result")
        with pytest.raises(ScraperError):
            SmartScraperWrapper().scrape("https://example.com", "Extract", api_key="fake")


# ─────────────────────────────────────────────
# SearchGraphWrapper
# ─────────────────────────────────────────────


def test_search_graph_wrapper_returns_list(mock_search_graph_sponsors_list: list[dict]) -> None:
    with patch("backend.tools.scraper_tool.SearchGraphWrapper.search") as mock_search:
        mock_search.return_value = mock_search_graph_sponsors_list
        wrapper = SearchGraphWrapper()
        result = wrapper.search("AI conference sponsors Europe", "Extract sponsors", api_key="fake")

    assert isinstance(result, list)
    assert len(result) == 2


# ─────────────────────────────────────────────
# scrape_event_page
# ─────────────────────────────────────────────


def test_scrape_event_page_returns_event_schema(mock_smart_scraper_event_dict: dict) -> None:
    with patch("backend.tools.scraper_tool.SmartScraperWrapper.scrape") as mock_scrape:
        mock_scrape.return_value = mock_smart_scraper_event_dict
        event = scrape_event_page("https://event.example.com", api_key="fake")

    assert isinstance(event, EventSchema)
    assert event.event_name == "AI Summit 2025"
    assert event.city == "Berlin"
    assert event.estimated_attendance == 800


def test_scrape_event_page_sets_source_url_if_missing() -> None:
    data = {
        "event_name": "Test Event",
        "date": "2025-01-01",
        "city": "Paris",
        "country": "FR",
        "category": "Tech",
    }
    url = "https://test.example.com"
    with patch("backend.tools.scraper_tool.SmartScraperWrapper.scrape") as mock_scrape:
        mock_scrape.return_value = data
        event = scrape_event_page(url, api_key="fake")

    assert event.source_url == url


# ─────────────────────────────────────────────
# scrape_venue_page
# ─────────────────────────────────────────────


def test_scrape_venue_page_returns_venue_schema() -> None:
    venue_dict = {
        "name": "Berlin Convention Center",
        "city": "Berlin",
        "country": "DE",
        "capacity": 3000,
        "price_range": "$10,000-$20,000/day",
        "past_events": ["Tech Expo 2024"],
    }
    with patch("backend.tools.scraper_tool.SmartScraperWrapper.scrape") as mock_scrape:
        mock_scrape.return_value = venue_dict
        from backend.models.schemas import VenueSchema

        venue = scrape_venue_page("https://venue.example.com", api_key="fake")

    assert isinstance(venue, VenueSchema)
    assert venue.city == "Berlin"
    assert venue.capacity == 3000


# ─────────────────────────────────────────────
# search_sponsors_structured
# ─────────────────────────────────────────────


def test_search_sponsors_structured_returns_sponsor_schema_list(
    mock_search_graph_sponsors_list: list[dict],
) -> None:
    with patch("backend.tools.scraper_tool.SearchGraphWrapper.search") as mock_search:
        mock_search.return_value = mock_search_graph_sponsors_list
        sponsors = search_sponsors_structured("AI", "Europe", api_key="fake")

    assert all(isinstance(s, SponsorSchema) for s in sponsors)
    assert sponsors[0].name == "TechCorp"


def test_search_sponsors_structured_skips_malformed_items() -> None:
    bad_list = [{"name": "Good"}, {"bad_field_only": "no name"}, {"name": "Also Good"}]
    with patch("backend.tools.scraper_tool.SearchGraphWrapper.search") as mock_search:
        mock_search.return_value = bad_list
        sponsors = search_sponsors_structured("AI", "EU", api_key="fake")

    # Malformed items are skipped, valid ones kept
    names = [s.name for s in sponsors]
    assert "Good" in names
    assert "Also Good" in names


# ─────────────────────────────────────────────
# search_speakers_structured
# ─────────────────────────────────────────────


def test_search_speakers_structured_returns_speaker_schema_list() -> None:
    speaker_list = [{"name": "Jane Doe", "topic": "LLMs", "region": "India"}]
    with patch("backend.tools.scraper_tool.SearchGraphWrapper.search") as mock_search:
        mock_search.return_value = speaker_list
        speakers = search_speakers_structured("AI", "India", api_key="fake")

    assert all(isinstance(s, SpeakerSchema) for s in speakers)
    assert speakers[0].name == "Jane Doe"


# ─────────────────────────────────────────────
# search_exhibitors_structured
# ─────────────────────────────────────────────


def test_search_exhibitors_structured_returns_exhibitor_schema_list() -> None:
    exhibitor_list = [{"name": "StartupXYZ", "cluster": "startup"}]
    with patch("backend.tools.scraper_tool.SearchGraphWrapper.search") as mock_search:
        mock_search.return_value = exhibitor_list
        exhibitors = search_exhibitors_structured("AI", api_key="fake")

    assert all(isinstance(e, ExhibitorSchema) for e in exhibitors)
    assert exhibitors[0].cluster == "startup"
