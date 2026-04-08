"""
conftest.py — Shared pytest fixtures for ConfMind tool tests.

All fixtures use only local data (no API calls).  External services
(Serper, ScrapeGraph-AI, RapidAPI, WeasyPrint) are mocked in each test file.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.models.schemas import (
    EventSchema,
    ExhibitorSchema,
    LinkedInProfile,
    SerperResult,
    SpeakerSchema,
    SponsorSchema,
    TicketTierSchema,
    VenueSchema,
)

# ─────────────────────────────────────────────
# Schema fixtures
# ─────────────────────────────────────────────


@pytest.fixture()
def sample_sponsor() -> SponsorSchema:
    return SponsorSchema(
        name="TechCorp",
        website="https://techcorp.example.com",
        industry="AI",
        geo="Europe",
        tier="Gold",
        relevance_score=8.5,
    )


@pytest.fixture()
def sample_speaker() -> SpeakerSchema:
    return SpeakerSchema(
        name="Jane Doe",
        bio="AI researcher and conference speaker.",
        linkedin_url="https://linkedin.com/in/janedoe",
        topic="Large Language Models",
        region="India",
        influence_score=0.0,
        speaking_experience=5,
    )


@pytest.fixture()
def sample_venue() -> VenueSchema:
    return VenueSchema(
        name="Tech Convention Center",
        city="Berlin",
        country="DE",
        capacity=2000,
        price_range="$10,000-$20,000/day",
        past_events=["AI Summit 2024", "Web3 Expo 2024"],
        score=7.5,
        source_url="https://venue.example.com",
    )


@pytest.fixture()
def sample_event() -> EventSchema:
    return EventSchema(
        event_name="AI Summit 2025",
        date="2025-09-15",
        city="Berlin",
        country="DE",
        category="AI",
        theme="The Future of LLMs",
        sponsors=["TechCorp", "CloudInc"],
        speakers=["Jane Doe", "John Smith"],
        ticket_price_early=99.0,
        ticket_price_general=149.0,
        ticket_price_vip=499.0,
        estimated_attendance=800,
        venue_name="Tech Convention Center",
        venue_capacity=2000,
        source_url="https://event.example.com",
    )


@pytest.fixture()
def sample_exhibitor() -> ExhibitorSchema:
    return ExhibitorSchema(name="StartupXYZ", cluster="startup", relevance=6.0)


@pytest.fixture()
def sample_tier() -> TicketTierSchema:
    return TicketTierSchema(name="General", price=150.0, est_sales=450, revenue=67500.0)


@pytest.fixture()
def sample_linkedin_profile() -> LinkedInProfile:
    return LinkedInProfile(
        name="Jane Doe",
        headline="AI Researcher at DeepMind",
        followers=25000,
        connections=500,
        recent_posts_count=8,
        linkedin_url="https://linkedin.com/in/janedoe",
    )


@pytest.fixture()
def sample_serper_result() -> SerperResult:
    return SerperResult(
        title="TechCorp sponsors AI Summit 2025",
        url="https://techcorp.example.com/events",
        snippet="TechCorp is a Gold sponsor of AI Summit 2025 in Berlin.",
        position=1,
    )


# ─────────────────────────────────────────────
# Serper API mock response fixture
# ─────────────────────────────────────────────


@pytest.fixture()
def mock_serper_response() -> dict:
    """Raw JSON body returned by Serper.dev /search endpoint."""
    return {
        "organic": [
            {
                "title": "TechCorp — AI Event Sponsor",
                "link": "https://techcorp.example.com",
                "snippet": "TechCorp sponsors European AI events.",
                "position": 1,
            },
            {
                "title": "CloudInc — Conference Partner",
                "link": "https://cloudinc.example.com",
                "snippet": "CloudInc is a leading cloud sponsor.",
                "position": 2,
            },
        ]
    }


# ─────────────────────────────────────────────
# ScrapeGraph-AI mock response fixtures
# ─────────────────────────────────────────────


@pytest.fixture()
def mock_smart_scraper_event_dict() -> dict:
    """Raw dict returned by SmartScraperGraph for an event page."""
    return {
        "event_name": "AI Summit 2025",
        "date": "2025-09-15",
        "city": "Berlin",
        "country": "DE",
        "category": "AI",
        "theme": "The Future of LLMs",
        "sponsors": ["TechCorp"],
        "speakers": ["Jane Doe"],
        "ticket_price_early": 99.0,
        "ticket_price_general": 149.0,
        "ticket_price_vip": 499.0,
        "estimated_attendance": 800,
        "venue_name": "Tech Convention Center",
        "venue_capacity": 2000,
        "source_url": "https://event.example.com",
    }


@pytest.fixture()
def mock_search_graph_sponsors_list() -> list[dict]:
    """Raw list returned by SearchGraph for a sponsor search."""
    return [
        {
            "name": "TechCorp",
            "website": "https://techcorp.example.com",
            "industry": "AI",
            "geo": "Europe",
        },
        {
            "name": "CloudInc",
            "website": "https://cloudinc.example.com",
            "industry": "Cloud",
            "geo": "USA",
        },
    ]


# ─────────────────────────────────────────────
# LinkedIn API mock response fixture
# ─────────────────────────────────────────────


@pytest.fixture()
def mock_linkedin_api_response() -> dict:
    """Raw JSON body returned by RapidAPI LinkedIn endpoint."""
    return {
        "full_name": "Jane Doe",
        "headline": "AI Researcher at DeepMind",
        "follower_count": 25000,
        "connection_count": 500,
        "posts_count": 8,
    }


# ─────────────────────────────────────────────
# Pricing model — sample training DataFrame
# ─────────────────────────────────────────────


@pytest.fixture()
def sample_events_df() -> pd.DataFrame:
    """20-row synthetic event DataFrame for training the pricing model."""
    import numpy as np

    rng = np.random.default_rng(42)
    n = 20
    categories = ["AI", "Web3", "ClimateTech", "Music", "Sports"]
    cities = ["Berlin", "Mumbai", "New York", "Singapore", "London"]
    return pd.DataFrame(
        {
            "category": rng.choice(categories, n),
            "ticket_price_general": rng.uniform(50, 500, n).round(2),
            "city": rng.choice(cities, n),
            "venue_capacity": rng.integers(200, 5000, n),
            "estimated_attendance": rng.integers(100, 3000, n),
        }
    )
