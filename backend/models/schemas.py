"""
schemas.py — Shared Pydantic v2 data models for ConfMind.

Every tool and agent imports from here.  This is the single source of truth for
all structured data flowing through the system.

Domain models
─────────────
EventSchema      Full event record (used by ETL pipeline + dataset)
SponsorSchema    A company / brand that sponsors events
SpeakerSchema    A conference speaker or artist
VenueSchema      A physical event location
ExhibitorSchema  A company showing products/services at an event
TicketTierSchema One ticket pricing tier (Early Bird / General / VIP)
CommunitySchema  An online community (Discord server, Slack, etc.)
SerperResult     A single Google search result returned by serper_tool
LinkedInProfile  Enriched LinkedIn data for a Person
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# ─────────────────────────────────────────────
# Search / Scraping primitives
# ─────────────────────────────────────────────


class SerperResult(BaseModel):
    """A single result returned by the Serper Google Search API."""

    title: str
    url: str
    snippet: str = ""
    position: int = Field(ge=1)


class LinkedInProfile(BaseModel):
    """Enriched LinkedIn profile data fetched via RapidAPI."""

    name: str
    headline: str = ""
    followers: int = Field(default=0, ge=0)
    connections: int = Field(default=0, ge=0)
    recent_posts_count: int = Field(default=0, ge=0)
    linkedin_url: str


# ─────────────────────────────────────────────
# Event / Conference domain models
# ─────────────────────────────────────────────


class SponsorSchema(BaseModel):
    """A company that sponsors events.  Produced by the scraper/serper tools,
    consumed by the Sponsor Agent."""

    name: str
    website: str = ""
    industry: str = ""
    geo: str = ""  # ISO country code or region name
    tier: str = "General"  # Gold / Silver / Bronze / General
    relevance_score: float = Field(default=0.0, ge=0.0, le=10.0)

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        allowed = {"Gold", "Silver", "Bronze", "General"}
        if v not in allowed:
            raise ValueError(f"tier must be one of {allowed}, got {v!r}")
        return v


class SpeakerSchema(BaseModel):
    """A conference speaker or artist."""

    name: str
    bio: str = ""
    linkedin_url: str = ""
    topic: str = ""
    region: str = ""
    influence_score: float = Field(default=0.0, ge=0.0, le=10.0)
    speaking_experience: int = Field(default=0, ge=0)  # number of past talks


class VenueSchema(BaseModel):
    """A physical event venue."""

    name: str
    city: str
    country: str = ""
    capacity: int | None = Field(default=None, ge=1)
    price_range: str = ""  # e.g. "$5,000-$15,000/day"
    past_events: list[str] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=10.0)
    source_url: str = ""


class ExhibitorSchema(BaseModel):
    """A company exhibiting at an event."""

    name: str
    cluster: str = ""  # startup / enterprise / tools / individual
    relevance: float = Field(default=0.0, ge=0.0, le=10.0)
    website: str = ""


class TicketTierSchema(BaseModel):
    """One ticket pricing tier with revenue projections."""

    name: str  # "Early Bird" | "General" | "VIP"
    price: float = Field(ge=0.0)
    est_sales: int = Field(default=0, ge=0)
    revenue: float = Field(default=0.0, ge=0.0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        allowed = {"Early Bird", "General", "VIP"}
        if v not in allowed:
            raise ValueError(f"name must be one of {allowed}, got {v!r}")
        return v


class CommunitySchema(BaseModel):
    """An online community targeted for GTM distribution."""

    platform: str  # Discord / Slack / Reddit / Telegram
    name: str
    size: int = Field(default=0, ge=0)  # member count
    niche: str = ""
    invite_url: str = ""


class EventSchema(BaseModel):
    """Full conference / event record — output of the ETL pipeline and stored in the dataset."""

    event_name: str
    date: str = ""  # ISO 8601 string: "2025-09-15"
    city: str = ""
    country: str = ""  # ISO 3166-1 alpha-2 e.g. "IN", "US"
    category: str = ""  # AI / Web3 / ClimateTech / Music / Sports …
    theme: str = ""
    sponsors: list[str] = Field(default_factory=list)
    speakers: list[str] = Field(default_factory=list)
    exhibitors: list[str] = Field(default_factory=list)
    ticket_price_early: float = Field(default=0.0, ge=0.0)
    ticket_price_general: float = Field(default=0.0, ge=0.0)
    ticket_price_vip: float = Field(default=0.0, ge=0.0)
    estimated_attendance: int = Field(default=0, ge=0)
    venue_name: str = ""
    venue_capacity: int | None = Field(default=None, ge=1)
    source_url: str = ""
