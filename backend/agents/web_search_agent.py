"""
web_search_agent.py — Web Search Agent for ConfMind.

Spawned N times in parallel by the Orchestrator. Each instance is assigned
a slice of events (via offset pagination) from PredictHQ, enriched by Tavily.

System Prompt:
  "You are a Web-Search Agent. Your ONLY job is to build high-quality
   past_events data using PredictHQ first, Tavily second. Be precise
   and category-aware."

Loop (max 3 passes per event):
  • Pass 1: PredictHQ Events API with assigned offset. Extract all required
            fields + entities (type=venue/performer/organizer).
  • Pass 2 (enrichment): For any event missing phq_attendance OR entities →
            Tavily query: "{event_title} {category} {geography} 2025 sponsors
            speakers exhibitors venue". Parse content.
  • Pass 3 (pricing): If still no pricing → Tavily "{event_title} ticket
            price 2025".

Output per event dict: {name, location, category, sponsors:[], speakers:[],
  exhibitors:[], venue_name, pricing:{}, attendance_estimate, phq_rank, source}.
  Missing fields = null. No further retries.

Stop: All assigned events done. Write delta to past_events.
"""

from __future__ import annotations

import os
import hashlib
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState
from .base_agent import BaseAgent


# ── Constants ──────────────────────────────────────────────────────────────────

_MAX_PASSES_PER_EVENT = 3
_PHQ_REQUIRED_FIELDS = [
    "title", "category", "phq_attendance", "predicted_event_spend",
    "entities", "location", "start", "rank", "place_hierarchies",
]


class WebSearchAgent(BaseAgent):
    """Builds high-quality past_events data using PredictHQ + Tavily.

    Each instance is assigned an offset and limit by the Orchestrator so that
    multiple instances can run in parallel, each covering a different page of
    PredictHQ results.

    Attributes:
        agent_id:  Integer ID (1..N) — used in name and logging.
        offset:    PredictHQ pagination offset.
        limit:     Number of events to fetch per page.
        category:  PredictHQ category string (mapped by Orchestrator).
        geography: Place scope string.
    """

    def __init__(
        self,
        agent_id: int = 1,
        offset: int = 0,
        limit: int = 10,
        category: str = "conferences",
        geography: str = "",
    ) -> None:
        self.agent_id = agent_id
        self.offset = offset
        self.limit = limit
        self.phq_category = category
        self.geography = geography
        self.name = f"web_search_agent_{agent_id}"

    # ── Prompt ────────────────────────────────────────────────────────────

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a Web-Search Agent for ConfMind. Your ONLY job is to build "
                    "high-quality past_events data using PredictHQ first, Tavily second.\n\n"
                    "CRITICAL RULES:\n"
                    "1. NEVER hallucinate event data — only extract what is explicitly stated.\n"
                    "2. Use PredictHQ as primary source, Tavily only to fill gaps.\n"
                    "3. Every event MUST have: name, location, category.\n"
                    "4. Missing fields = null. Do NOT guess.\n"
                    "5. Be category-aware: use correct terminology for {category}.\n"
                    "6. Sponsors, speakers, exhibitors are LISTS of strings.\n"
                    "7. Pricing is a dict: {{early_bird: float, general: float, vip: float}}.\n"
                    "8. Output ONLY valid JSON. No prose before or after.",
                ),
                ("human", "{input}"),
            ]
        )

    # ── PredictHQ fetch ───────────────────────────────────────────────────

    def _fetch_predicthq_events(self) -> list[dict[str, Any]]:
        """Fetch events from PredictHQ Events API using the official SDK.

        Uses phq.events.search() with required fields, paginated by
        self.offset and self.limit.
        """
        try:
            from predicthq import Client  # type: ignore[import-untyped]
        except ImportError:
            self._log_info("PredictHQ SDK not installed — skipping PHQ fetch")
            return []

        api_key = os.getenv("PREDICTHQ_API_KEY", "")
        if not api_key:
            self._log_info("PREDICTHQ_API_KEY not set — skipping PHQ fetch")
            return []

        try:
            phq = Client(access_token=api_key)
            events_result = phq.events.search(
                category=self.phq_category,
                q=self.geography if self.geography else None,
                active__gte="2025-01-01",
                limit=self.limit,
                offset=self.offset,
            )

            events = []
            for event in events_result:
                event_dict = {
                    "name": getattr(event, "title", None),
                    "category": getattr(event, "category", None),
                    "phq_attendance": getattr(event, "phq_attendance", None),
                    "predicted_event_spend": getattr(event, "predicted_event_spend", None),
                    "location": None,
                    "start": str(getattr(event, "start", "")),
                    "phq_rank": getattr(event, "rank", None),
                    "entities": [],
                    "venue_name": None,
                    "sponsors": [],
                    "speakers": [],
                    "exhibitors": [],
                    "pricing": {},
                    "attendance_estimate": getattr(event, "phq_attendance", None),
                    "source": "predicthq",
                }

                # Extract location
                loc = getattr(event, "location", None)
                if loc:
                    event_dict["location"] = str(loc)

                # Extract entities (venue/performer/organizer)
                entities = getattr(event, "entities", [])
                if entities:
                    for ent in entities:
                        ent_type = getattr(ent, "type", "")
                        ent_name = getattr(ent, "name", "")
                        if ent_type == "venue":
                            event_dict["venue_name"] = ent_name
                        elif ent_type == "performer":
                            event_dict["speakers"].append(ent_name)
                        elif ent_type == "organizer":
                            event_dict["sponsors"].append(ent_name)
                        event_dict["entities"].append({"type": ent_type, "name": ent_name})

                # Extract place hierarchies for location
                ph = getattr(event, "place_hierarchies", [])
                if ph and not event_dict["location"]:
                    event_dict["location"] = str(ph[0]) if ph[0] else None

                events.append(event_dict)

            self._log_info(f"PredictHQ returned {len(events)} events")
            return events

        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "429" in err_str:
                self._log_info(f"PredictHQ {err_str[:50]}  — switching to Tavily-only")
            else:
                self._log_info(f"PredictHQ fetch failed: {e}")
            return []

    # ── Enrichment pass via Tavily ────────────────────────────────────────

    def _enrich_event_tavily(self, event: dict[str, Any], category: str, geography: str) -> dict[str, Any]:
        """Pass 2: Enrich event with missing data via Tavily."""
        name = event.get("name", "")
        if not name:
            return event

        # Only enrich if missing attendance or entities
        needs_enrichment = (
            not event.get("phq_attendance")
            or not event.get("entities")
            or not event.get("sponsors")
        )

        if not needs_enrichment:
            return event

        query = f"{name} {category} {geography} 2025 sponsors speakers exhibitors venue"
        results = self._tavily_search(query, max_results=3)

        if results:
            # Use LLM to extract structured data from Tavily content
            combined_content = "\n".join(r.get("content", "") for r in results)
            extraction_prompt = (
                f"From the following text about the event '{name}', extract:\n"
                f"- sponsors (list of company names)\n"
                f"- speakers (list of person names)\n"
                f"- exhibitors (list of company names)\n"
                f"- venue_name (string)\n"
                f"- attendance_estimate (integer)\n\n"
                f"Text:\n{combined_content[:3000]}\n\n"
                f"Output ONLY valid JSON. Missing fields = null."
            )
            extracted = self._invoke_llm_json(extraction_prompt)
            if extracted and isinstance(extracted, dict):
                if not event.get("sponsors") and extracted.get("sponsors"):
                    event["sponsors"] = extracted["sponsors"]
                if not event.get("speakers") and extracted.get("speakers"):
                    event["speakers"] = extracted["speakers"]
                if not event.get("exhibitors") and extracted.get("exhibitors"):
                    event["exhibitors"] = extracted["exhibitors"]
                if not event.get("venue_name") and extracted.get("venue_name"):
                    event["venue_name"] = extracted["venue_name"]
                if not event.get("attendance_estimate") and extracted.get("attendance_estimate"):
                    event["attendance_estimate"] = extracted["attendance_estimate"]

        return event

    def _enrich_pricing_tavily(self, event: dict[str, Any]) -> dict[str, Any]:
        """Pass 3: If still no pricing, try Tavily for ticket prices."""
        name = event.get("name", "")
        if not name or event.get("pricing"):
            return event

        query = f"{name} ticket price 2025"
        results = self._tavily_search(query, max_results=2)

        if results:
            combined = "\n".join(r.get("content", "") for r in results)
            extraction_prompt = (
                f"From the following text about '{name}', extract ticket pricing:\n"
                f"- early_bird (float, USD)\n"
                f"- general (float, USD)\n"
                f"- vip (float, USD)\n\n"
                f"Text:\n{combined[:2000]}\n\n"
                f"Output ONLY valid JSON like: {{\"early_bird\": 99.0, \"general\": 199.0, \"vip\": 499.0}}\n"
                f"If price not found, use null."
            )
            pricing = self._invoke_llm_json(extraction_prompt)
            if pricing and isinstance(pricing, dict):
                event["pricing"] = pricing

        return event

    # ── Main run ──────────────────────────────────────────────────────────

    def run(self, state: AgentState) -> dict[str, Any]:
        """Execute the 3-pass loop for assigned events."""
        self._current_pass = 0
        self._log_info(f"Starting (offset={self.offset}, limit={self.limit}, category={self.phq_category})")

        try:
            cfg = state.get("event_config")
            category = cfg.category if cfg else self.phq_category
            geography = cfg.geography if cfg else self.geography

            # ── Pass 1: PredictHQ Events API ──────────────────────────────────
            with self._pass_context(
                "Pass 1: PredictHQ fetch", state,
                f"past events for {category} in {geography}"
            ):
                events = self._fetch_predicthq_events()

                # Fallback: if PredictHQ returned nothing, try Tavily discovery
                if not events:
                    self._log_info("PHQ returned 0 events — trying Tavily discovery fallback")
                    fallback_query = f"{category} events {geography} 2025 2026"
                    tavily_results = self._tavily_search(fallback_query, max_results=5)
                    for r in tavily_results:
                        events.append({
                            "name": r.get("content", "")[:100].split(".")[0].strip(),
                            "location": geography,
                            "category": category,
                            "sponsors": [],
                            "speakers": [],
                            "exhibitors": [],
                            "venue_name": None,
                            "pricing": {},
                            "attendance_estimate": None,
                            "phq_rank": None,
                            "source": "tavily_fallback",
                        })

            # ── Pass 2: Tavily enrichment ─────────────────────────────────────
            with self._pass_context(
                "Pass 2: Tavily enrichment", state,
                f"enriching {len(events)} events"
            ):
                for i, event in enumerate(events):
                    events[i] = self._enrich_event_tavily(event, category, geography)

            # ── Pass 3: Pricing enrichment ────────────────────────────────────
            with self._pass_context(
                "Pass 3: Pricing enrichment", state,
                f"pricing for {category} events"
            ):
                for i, event in enumerate(events):
                    events[i] = self._enrich_pricing_tavily(event)

            # ── Write to memory ───────────────────────────────────────────────
            docs = [
                f"{e.get('name', 'unknown')} | {e.get('location', '')} | {e.get('category', '')}"
                for e in events
            ]
            meta = [{"agent_id": self.agent_id, "source": e.get("source", "unknown")} for e in events]
            if docs:
                self._write_memory(docs, meta, collection="events")

            self._log_info(f"Completed — {len(events)} events processed")

            return {"past_events": events}

        except Exception as exc:
            return self._log_error(state, f"WebSearchAgent[{self.agent_id}] failed: {exc}")
