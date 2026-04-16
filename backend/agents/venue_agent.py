"""
venue_agent.py — Venue discovery and scoring agent for ConfMind.

System Prompt:
  "You are the Venue Agent. Use PredictHQ history first, then enrich."

Loop (4 passes):
  • Pass 1: PredictHQ Events (same geography + category) → extract
            type=venue entities.
  • Pass 2: Tavily "{venue_name} {city} capacity pricing past events".
  • Pass 3: New candidates via "best venues {city} {category}
            {target_size} attendees".
  • Pass 4: Score & rank top 5.

Stop: ≥5 venues or one radius expansion.
"""

from __future__ import annotations

import os
from collections import Counter
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState, VenueSchema

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_TARGET_VENUES = 5
_MAX_RADIUS_EXPANSIONS = 1


class VenueAgent(BaseAgent):
    """Discovers, enriches, and ranks event venues.

    Sources:
        1. past_events venue entities from WebSearchAgent
        2. PredictHQ venue entity extraction (same geography + category)
        3. Tavily enrichment for capacity/pricing
        4. Tavily discovery for new venue candidates

    Output:
        state["venues"] — top 5 VenueSchema list, scored and ranked
    """

    name: str = "venue_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are the Venue Agent for ConfMind. You find the best venues "
                    "for events using historical data first, then enriching with web search.\n\n"
                    "CRITICAL RULES:\n"
                    "1. Use PredictHQ history as the primary source for venue discovery.\n"
                    "2. Prioritize venues that have hosted similar events before.\n"
                    "3. Capacity match is critical: venue capacity should be within "
                    "50% of the target audience size.\n"
                    "4. Geographic fit: prefer venues in the target city/region.\n"
                    "5. Cost data from Tavily is supplementary — normalize to USD.\n"
                    "6. Score venues on: capacity fit (40%), location (25%), "
                    "past event history (20%), cost efficiency (15%).\n"
                    "7. NEVER hallucinate venue details. Missing data = null.\n"
                    "8. Output valid JSON when asked.",
                ),
                ("human", "{input}"),
            ]
        )

    # ── Pass 1: Extract venues from past_events + PredictHQ ───────────────

    def _extract_venues(self, past_events: list[dict]) -> list[dict[str, Any]]:
        """Extract venue data from past_events."""
        venue_counter: Counter = Counter()
        venue_meta: dict[str, dict] = {}

        for event in past_events:
            venue_name = event.get("venue_name")
            if venue_name and isinstance(venue_name, str) and venue_name.strip():
                name = venue_name.strip()
                venue_counter[name] += 1
                if name not in venue_meta:
                    venue_meta[name] = {
                        "location": event.get("location", ""),
                        "categories": set(),
                        "attendance": event.get("attendance_estimate"),
                    }
                cat = event.get("category", "")
                if cat:
                    venue_meta[name]["categories"].add(cat)
                # Update attendance if higher
                att = event.get("attendance_estimate")
                if att and (
                    not venue_meta[name]["attendance"]
                    or att > venue_meta[name]["attendance"]
                ):
                    venue_meta[name]["attendance"] = att

        venues = []
        for name, count in venue_counter.most_common():
            meta = venue_meta.get(name, {})
            venues.append({
                "name": name,
                "frequency": count,
                "location": meta.get("location", ""),
                "categories": list(meta.get("categories", [])),
                "capacity": meta.get("attendance"),
                "price_range": "",
                "source": "past_events",
                "enrichment": {},
            })

        self._log_info(f"Extracted {len(venues)} unique venues from past events")
        return venues

    def _fetch_phq_venues(self, category: str, geography: str) -> list[dict[str, Any]]:
        """Fetch venue entities directly from PredictHQ."""
        try:
            from predicthq import Client  # type: ignore[import-untyped]
        except ImportError:
            return []

        api_key = os.getenv("PREDICTHQ_API_KEY", "")
        if not api_key:
            return []

        try:
            phq = Client(access_token=api_key)
            events_result = phq.events.search(
                category=category,
                q=geography if geography else None,
                active__gte="2025-01-01",
                limit=10,
            )

            venues = []
            seen = set()
            for event in events_result:
                entities = getattr(event, "entities", [])
                for ent in entities:
                    if getattr(ent, "type", "") == "venue":
                        name = getattr(ent, "name", "")
                        if name and name not in seen:
                            seen.add(name)
                            venues.append({
                                "name": name,
                                "frequency": 1,
                                "location": str(getattr(event, "location", "")),
                                "categories": [category],
                                "capacity": None,
                                "price_range": "",
                                "source": "predicthq",
                                "enrichment": {},
                            })

            self._log_info(f"PredictHQ returned {len(venues)} venue entities")
            return venues

        except Exception as e:
            self._log_info(f"PredictHQ venue fetch failed: {e}")
            return []

    # ── Pass 2: Tavily enrichment ─────────────────────────────────────────

    def _enrich_venues(self, venues: list[dict], city: str) -> list[dict]:
        """Enrich venues with capacity and pricing data via Tavily."""
        for venue in venues[:10]:  # Enrich top 10
            name = venue["name"]
            query = f"{name} {city} capacity pricing past events conference"
            results = self._tavily_search(query, max_results=3)

            if results:
                combined = "\n".join(r.get("content", "") for r in results)
                extract_prompt = (
                    f"From the following text about the venue '{name}', extract:\n"
                    f"- capacity (integer, max attendees)\n"
                    f"- price_range (string like '$5,000-$15,000/day')\n"
                    f"- city (string)\n"
                    f"- country (string)\n"
                    f"- past_events (list of event names held there)\n\n"
                    f"Text: {combined[:2000]}\n\n"
                    f"Output ONLY valid JSON. Missing fields = null."
                )
                extracted = self._invoke_llm_json(extract_prompt)
                if extracted and isinstance(extracted, dict):
                    if extracted.get("capacity") and not venue["capacity"]:
                        try:
                            venue["capacity"] = int(extracted["capacity"])
                        except (ValueError, TypeError):
                            pass
                    if extracted.get("price_range"):
                        venue["price_range"] = extracted["price_range"]
                    venue["enrichment"] = {
                        "city": extracted.get("city", ""),
                        "country": extracted.get("country", ""),
                        "past_events": extracted.get("past_events", []),
                    }
                    self._log_info(f"  Enriched: {name}")

        return venues

    # ── Pass 3: Discover new candidates ───────────────────────────────────

    def _discover_new_venues(
        self, existing: list[dict], city: str, category: str, target_size: int
    ) -> list[dict]:
        """Discover new venue candidates via Tavily if needed."""
        if len(existing) >= _TARGET_VENUES:
            return existing

        query = f"best venues {city} {category} {target_size} attendees conference"
        results = self._tavily_search(query, max_results=5)

        if results:
            combined = "\n".join(r.get("content", "") for r in results)
            extract_prompt = (
                f"From the following text, extract venue names and details for "
                f"{category} events in {city}.\n\n"
                f"Text: {combined[:3000]}\n\n"
                f"Output as JSON array: [{{\"name\": \"...\", \"capacity\": 1000, "
                f"\"price_range\": \"...\", \"city\": \"...\"}}]\n"
                f"Output ONLY valid JSON."
            )
            venue_data = self._invoke_llm_json(extract_prompt)
            if venue_data and isinstance(venue_data, list):
                existing_names = {v["name"].lower() for v in existing}
                for vd in venue_data:
                    if isinstance(vd, dict):
                        name = vd.get("name", "")
                        if name and name.lower() not in existing_names:
                            existing.append({
                                "name": name,
                                "frequency": 0,
                                "location": vd.get("city", city),
                                "categories": [category],
                                "capacity": vd.get("capacity"),
                                "price_range": vd.get("price_range", ""),
                                "source": "tavily_discovery",
                                "enrichment": {},
                            })
                            existing_names.add(name.lower())

        self._log_info(f"After discovery: {len(existing)} venues")
        return existing

    # ── Pass 4: Score & rank ──────────────────────────────────────────────

    def _score_venues(
        self,
        venues: list[dict],
        target_size: int,
        geography: str,
    ) -> list[dict]:
        """Score venues using weighted criteria."""
        for venue in venues:
            # ── Capacity fit (40%) — 0-10 ─────────────────────────────────
            capacity = venue.get("capacity")
            if capacity and target_size > 0:
                ratio = capacity / target_size
                if 0.8 <= ratio <= 1.5:
                    cap_score = 10.0
                elif 0.5 <= ratio <= 2.0:
                    cap_score = 7.0
                else:
                    cap_score = max(0, 10 - abs(ratio - 1.0) * 5)
            else:
                cap_score = 5.0  # Unknown capacity → middle ground

            # ── Location fit (25%) — 0-10 ─────────────────────────────────
            location = str(venue.get("location", "")).lower()
            geo_lower = geography.lower()
            loc_score = 10.0 if geo_lower in location else 3.0

            # ── Past event history (20%) — 0-10 ──────────────────────────
            freq = venue.get("frequency", 0)
            hist_score = min(10.0, freq * 3.0)

            # ── Cost efficiency (15%) — 0-10 ─────────────────────────────
            price = venue.get("price_range", "")
            cost_score = 5.0  # Default
            if price:
                # Basic heuristic: if price is mentioned, score slightly higher
                cost_score = 6.0

            # ── Weighted composite ────────────────────────────────────────
            composite = (
                0.40 * cap_score
                + 0.25 * loc_score
                + 0.20 * hist_score
                + 0.15 * cost_score
            )
            venue["score"] = round(min(10.0, composite), 2)

        return venues

    # ── Main run ──────────────────────────────────────────────────────────

    def run(self, state: AgentState) -> dict[str, Any]:
        """Execute the 4-pass venue discovery pipeline."""
        self._current_pass = 0
        self._log_info("Starting venue discovery run...")

        try:
            cfg = state["event_config"]
            city = cfg.geography
            category = cfg.category
            target_size = cfg.audience_size
            past_events = state.get("past_events", [])

            # ── Pass 1: Extract from past_events + PredictHQ ──────────────
            with self._pass_context(
                "Pass 1: Extract venues", state,
                f"venues for {category} in {city}"
            ):
                venues = self._extract_venues(past_events)
                # Merge with PredictHQ venue entities
                phq_venues = self._fetch_phq_venues(category, city)
                existing_names = {v["name"].lower() for v in venues}
                for pv in phq_venues:
                    if pv["name"].lower() not in existing_names:
                        venues.append(pv)
                        existing_names.add(pv["name"].lower())

            # ── Pass 2: Tavily enrichment ─────────────────────────────────
            with self._pass_context(
                "Pass 2: Tavily enrichment", state,
                f"enriching venues in {city}"
            ):
                venues = self._enrich_venues(venues, city)

            # ── Pass 3: Discover new candidates if needed ─────────────────
            with self._pass_context(
                "Pass 3: Discover new candidates", state,
                f"venue candidates in {city} for {target_size} attendees"
            ):
                venues = self._discover_new_venues(venues, city, category, target_size)

                # One radius expansion if still not enough
                if len(venues) < _TARGET_VENUES:
                    self._log_info("Radius expansion: searching broader region")
                    venues = self._discover_new_venues(
                        venues, f"{city} region", category, target_size
                    )

            # ── Pass 4: Score & rank ──────────────────────────────────────
            with self._pass_context(
                "Pass 4: Score & rank", state,
                f"ranking venues for {category}"
            ):
                venues = self._score_venues(venues, target_size, city)
                venues.sort(key=lambda v: v.get("score", 0), reverse=True)
                venues = venues[:_TARGET_VENUES]

            # ── Build output VenueSchema list ─────────────────────────────
            venue_schemas = []
            for v in venues:
                enrichment = v.get("enrichment", {})
                past_events_list = enrichment.get("past_events", [])
                if not isinstance(past_events_list, list):
                    past_events_list = []

                venue_schemas.append(VenueSchema(
                    name=v["name"],
                    city=v.get("location", city) or city,
                    country=enrichment.get("country", ""),
                    capacity=v.get("capacity"),
                    price_range=v.get("price_range", ""),
                    past_events=[str(e) for e in past_events_list][:5],
                    score=v.get("score", 0),
                    source_url="",
                ))

            # Write to memory
            docs = [f"Venue: {v.name} | City: {v.city} | Score: {v.score}" for v in venue_schemas]
            meta = [{"name": v.name, "city": v.city, "score": v.score} for v in venue_schemas]
            self._write_memory(docs, meta, collection="venues")

            # Chat Agent Indexing Contract
            run_id = state.get("metadata", {}).get("run_id", "unknown")
            chat_docs = []
            chat_meta = []
            for v in venue_schemas:
                past_events_count = len(v.past_events)
                cost_tier = v.price_range if v.price_range else "Unknown"
                text = (
                    f"{v.name}. City: {v.city}. Capacity: {v.capacity}. "
                    f"Cost tier: {cost_tier}. Past events: {past_events_count}. Fit score: {v.score}"
                )
                chat_docs.append(text)
                chat_meta.append({
                    "agent": "venue",
                    "run_id": run_id,
                })
            self.index_to_chroma(chat_docs, "chat_index", chat_meta)

            self._log_info(f"Completed — {len(venue_schemas)} venues ranked")

            return {"venues": venue_schemas}


        except Exception as exc:
            return self._log_error(state, f"VenueAgent failed: {exc}")
