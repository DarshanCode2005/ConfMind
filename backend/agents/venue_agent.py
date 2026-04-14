"""
venue_agent.py — Venue discovery agent for ConfMind.

Fetches venue candidates from Serper and ScrapeGraph-AI.
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState, VenueSchema
from backend.tools.scraper_tool import scrape_venue_page
from backend.tools.serper_tool import search_venues

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_TOP_N = 5


class VenueAgent(BaseAgent):
    """Discovers and evaluates event venues."""

    name: str = "venue_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a venue sourcing specialist. You find the best locations for conferences "
                    "based on city, capacity, and suitability for the event type.",
                ),
                ("human", "{input}"),
            ]
        )

    def run(self, state: AgentState) -> AgentState:
        try:
            cfg = state["event_config"]
            city = cfg.geography
            event_type = cfg.category
            target_capacity = cfg.audience_size

            # ── 1. Search for venues via Serper ────────────────────────────────
            serper_results = search_venues(city, event_type)
            venues: list[VenueSchema] = []

            # ── 2. Scrape top results for details ──────────────────────────────
            for result in serper_results[:3]: # Scrape top 3 for detail
                try:
                    venue = scrape_venue_page(result.url)
                    # Use serper title/city if scraper missed it
                    if not venue.name or venue.name == "Unknown":
                        venue.name = result.title
                    if not venue.city:
                        venue.city = city
                    venues.append(venue)
                except Exception:
                    # Fallback to a stub if scraping fails
                    venues.append(VenueSchema(
                        name=result.title,
                        city=city,
                        source_url=result.url
                    ))

            # Add remaining serper results as stubs
            seen_urls = {v.source_url for v in venues}
            for result in serper_results[3:]:
                if result.url not in seen_urls:
                    venues.append(VenueSchema(
                        name=result.title,
                        city=city,
                        source_url=result.url
                    ))

            # ── 3. Simple scoring based on capacity match ─────────────────────
            for v in venues:
                if v.capacity:
                    # Score 0-10 based on how well capacity matches target
                    # 1.0 (perfect match) down to 0 (way off)
                    diff = abs(v.capacity - target_capacity)
                    v.score = max(0, 10 - (diff / target_capacity * 10))
                else:
                    v.score = 5.0 # Middle ground for unknown capacity

            ranked = sorted(venues, key=lambda x: x.score, reverse=True)[:_TOP_N]

            # ── 5. Write results ──────────────────────────────────────────────
            return {"venues": ranked}

        except Exception as exc:
            return self._log_error({}, f"VenueAgent failed: {exc}")
