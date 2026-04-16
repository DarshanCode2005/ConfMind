"""
schemas.py — Shared Pydantic v2 data models for ConfMind.

Every tool and agent imports from here.  This is the single source of truth for
all structured data flowing through the system.

Domain models
─────────────
EventSchema         Full event record (used by ETL pipeline + dataset)
SponsorSchema       A company / brand that sponsors events
SpeakerSchema       A conference speaker or artist
VenueSchema         A physical event location
ExhibitorSchema     A company showing products/services at an event
TicketTierSchema    One ticket pricing tier (Early Bird / General / VIP)
CommunitySchema     An online community (Discord server, Slack, etc.)
SerperResult        A single Google search result returned by serper_tool
LinkedInProfile     Enriched LinkedIn data for a Person

Orchestration contracts (LangGraph)
────────────────────────────────────
EventConfigInput    The user's event configuration submitted via the UI/API
AgentState          The shared TypedDict flowing through the LangGraph graph
                    Every agent reads from and writes to this object.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any

from langgraph.graph.message import add_messages  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, field_validator
from typing_extensions import TypedDict

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
    city: str | None = None
    country: str | None = None
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


# ─────────────────────────────────────────────
# Orchestration contracts (LangGraph)
# ─────────────────────────────────────────────


class EventConfigInput(BaseModel):
    """User event configuration submitted via the UI or REST API.

    This is the entry point — the user fills in these fields through the
    Next.js input wizard, and the API passes them to the LangGraph orchestrator.

    Fields
    ──────
    category       Type of event — "AI", "Web3", "ClimateTech", "Music", "Sports"
    geography      Target region — "Europe", "India", "USA", "Singapore"
    audience_size  Expected number of attendees
    budget_usd     Total event budget in USD
    event_dates    Target event date in ISO 8601 format ("2025-09-15")
    event_name     Optional custom event name; defaults to "{category} Summit"
    """

    category: str
    geography: str
    audience_size: int = Field(ge=1)
    budget_usd: float = Field(ge=0.0)
    event_dates: str  # ISO 8601 "YYYY-MM-DD"
    event_name: str = ""  # optional; agents fall back to "{category} Summit"


class ChatInput(BaseModel):
    """Input for the POST /chat endpoint."""

    session_id: str
    message: str
    plan_id: str | None = None


class AgentState(TypedDict):
    """Shared mutable state flowing through the LangGraph graph.

    The orchestrator initialises this from an EventConfigInput.
    Each agent node receives the full state, reads what it needs, writes
    its outputs into the relevant fields, and returns the updated state.

    Agents ONLY return the keys they modify using operator.add / operator.ior.
    No agent calls another agent's tools.

    Layout
    ──────
    event_config   Immutable user input — agents READ only
    past_events    Written by Web Search Agents (N parallel instances)
    sponsors       Written by Sponsor Agent
    speakers       Written by Speaker Agent
    venues         Written by Venue Agent
    exhibitors     Written by Exhibitor Agent
    pricing        Written by Pricing & Footfall Agent
    communities    Written by Community GTM Agent
    schedule       Written by Event Ops Agent
    revenue        Written by Revenue Agent
    gtm_messages   Written by Community GTM Agent (platform -> [message variants])
    messages       LangGraph message history (used for LLM call logging)
    errors         Any agent can append an error string here; orchestrator skips
    metadata       Free-form dict for agent-specific extras (proposal paths, etc.)
    """

    event_config: EventConfigInput
    past_events: Annotated[list[dict[str, Any]], operator.add]
    sponsors: list[SponsorSchema]
    speakers: list[SpeakerSchema]
    venues: list[VenueSchema]
    exhibitors: list[ExhibitorSchema]
    pricing: list[TicketTierSchema]
    communities: list[CommunitySchema]
    schedule: list[dict[str, Any]]
    revenue: dict[str, Any]
    gtm_messages: dict[str, Any]
    messages: Annotated[list[Any], add_messages]
    errors: Annotated[list[str], operator.add]
    metadata: Annotated[dict[str, Any], operator.ior]


class ChatState(TypedDict):
    """A lightweight separate state for the Chat Agent."""

    chat_history: list[dict[str, str]]
    run_id: str
    current_summary: str
    pending_rerun: dict[str, Any] | None
