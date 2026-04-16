"""
sponsor_agent.py — Sponsor discovery, enrichment, scoring, and proposal agent.

System Prompt:
  "You are the Sponsor Agent. Extract, enrich, score, and propose.
   Use historical data only for scoring."

Loop (5 passes):
  • Pass 1: Extract sponsors from past_events → deduplicate.
  • Pass 2: For top 20 by frequency → Tavily "{sponsor_name} event
            sponsorship {geography} 2025 marketing spend".
  • Pass 3: PredictHQ Entity Xref → Search company as entity, find related
            entities and categories.
  • Pass 4: Score = 0.35*industry_relevance + 0.25*geography_match
            + 0.25*frequency_norm + 0.15*spend_proxy_norm.
  • Pass 5: Top 3 → generate markdown proposal.

Stop: Top 15 scored. One retry per sponsor if enrichment fails.
"""

from __future__ import annotations

import os
import json
from collections import Counter
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState, SponsorSchema
from backend.tools.pdf_generator import save_proposal

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_TOP_N = 10         # how many sponsors to keep in final output
_ENRICH_TOP = 15     # how many to enrich via Tavily
_PROPOSAL_TOP = 3    # how many PDF proposals to generate

# Scoring weights per spec
_W_INDUSTRY = 0.35
_W_GEO = 0.25
_W_FREQUENCY = 0.25
_W_SPEND = 0.15


class SponsorAgent(BaseAgent):
    """Discovers, enriches, scores, and ranks conference sponsors.

    Sources:
        1. past_events from WebSearchAgent (primary)
        2. Tavily enrichment for top candidates
        3. PredictHQ Entity Xref for industry alignment
        4. LLM for industry relevance scoring

    Output:
        state["sponsors"]  — top-N SponsorSchema list, sorted by relevance_score
        state["metadata"]  — proposal_<name> keys with PDF paths for top 3
    """

    name: str = "sponsor_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are the Sponsor Agent for ConfMind. Your job is to extract, "
                    "enrich, score, and propose sponsors for an upcoming event.\n\n"
                    "CRITICAL RULES:\n"
                    "1. Extract sponsors ONLY from provided past_events data — never hallucinate.\n"
                    "2. Use historical sponsorship data for scoring — not speculation.\n"
                    "3. Industry relevance is judged by alignment between sponsor's "
                    "industry and the event category.\n"
                    "4. Geography match: sponsors operating in the target region score higher.\n"
                    "5. Frequency: sponsors appearing in multiple past events are more reliable.\n"
                    "6. Spend proxy: if Tavily mentions marketing spend or sponsorship amount, "
                    "normalize it.\n"
                    "7. Top 3 sponsors get a markdown proposal draft.\n"
                    "8. Always output valid JSON when asked. Missing data = null.",
                ),
                ("human", "{input}"),
            ]
        )

    # ── Pass 1: Extract from past_events ──────────────────────────────────

    def _extract_sponsors(self, past_events: list[dict]) -> list[dict[str, Any]]:
        """Extract all sponsor names from past_events, count frequency."""
        sponsor_counter: Counter = Counter()
        sponsor_meta: dict[str, dict] = {}  # name -> {locations, categories}

        for event in past_events:
            sponsors = event.get("sponsors", [])
            if isinstance(sponsors, list):
                location = event.get("location", "")
                category = event.get("category", "")
                for s in sponsors:
                    if isinstance(s, str) and s.strip():
                        name = s.strip()
                        sponsor_counter[name] += 1
                        if name not in sponsor_meta:
                            sponsor_meta[name] = {"locations": set(), "categories": set()}
                        if location:
                            sponsor_meta[name]["locations"].add(str(location))
                        if category:
                            sponsor_meta[name]["categories"].add(str(category))

        sponsors = []
        for name, count in sponsor_counter.most_common():
            meta = sponsor_meta.get(name, {})
            sponsors.append({
                "name": name,
                "frequency": count,
                "locations": list(meta.get("locations", [])),
                "categories": list(meta.get("categories", [])),
                "enrichment": {},
            })

        self._log_info(f"Extracted {len(sponsors)} unique sponsors from past events")
        return sponsors

    # ── Pass 2: Tavily enrichment ─────────────────────────────────────────

    def _enrich_sponsors(self, sponsors: list[dict], geography: str) -> list[dict]:
        """Enrich top sponsors with Tavily search data."""
        for sponsor in sponsors[:_ENRICH_TOP]:
            name = sponsor["name"]
            query = f"{name} event sponsorship {geography} 2025 marketing spend"
            results = self._tavily_search(query, max_results=3)

            if results:
                combined = "\n".join(r.get("content", "") for r in results)
                sponsor["enrichment"] = {
                    "raw_content": combined[:2000],
                    "source_urls": [r.get("url", "") for r in results],
                }
                self._log_info(f"  Enriched: {name}")
            else:
                self._log_info(f"  No enrichment data for: {name}")

        return sponsors

    # ── Pass 3: PredictHQ Entity Xref ─────────────────────────────────────

    def _phq_entity_xref(self, sponsors: list[dict]) -> list[dict]:
        """Cross-reference sponsors with PredictHQ entities to find related categories."""
        try:
            from predicthq import Client  # type: ignore[import-untyped]
        except ImportError:
            return sponsors

        api_key = os.getenv("PREDICTHQ_API_KEY", "")
        if not api_key:
            return sponsors

        phq = Client(access_token=api_key)
        for sponsor in sponsors[:_ENRICH_TOP]:
            name = sponsor["name"]
            try:
                # Search for the sponsor as an entity
                entity_results = phq.entities.search(q=name, type="organization")
                for entity in entity_results:
                    if getattr(entity, "name", "").lower() == name.lower():
                        # Enrich with industry info from PHQ if found
                        phq_industry = getattr(entity, "industry", None)
                        if phq_industry:
                            sponsor["categories"].append(phq_industry)
                        self._log_info(f"  PHQ Xref found for: {name}")
                        break
            except Exception:
                continue

        return sponsors

    # ── Pass 4: Scoring ───────────────────────────────────────────────────

    def _score_sponsors(
        self,
        sponsors: list[dict],
        category: str,
        geography: str,
        max_frequency: int,
    ) -> list[dict]:
        """Score each sponsor using the weighted formula from spec."""

        for sponsor in sponsors:
            # ── Industry relevance via LLM (0-10) ─────────────────────────
            enrichment_text = sponsor.get("enrichment", {}).get("raw_content", "")
            cats = ", ".join(sponsor.get("categories", []))
            industry_prompt = (
                f"Rate the industry relevance (0-10) of the company '{sponsor['name']}' "
                f"for a '{category}' event. Known categories they sponsor: {cats}. "
                f"Additional context: {enrichment_text[:500]}\n\n"
                f"Output ONLY a single number between 0 and 10."
            )
            industry_raw = self._invoke_llm(industry_prompt, temperature=0.1)
            try:
                industry_score = min(10.0, max(0.0, float(industry_raw)))
            except (ValueError, TypeError):
                industry_score = 5.0  # Default mid-range

            # ── Geography match (0-10) ────────────────────────────────────
            locations = [loc.lower() for loc in sponsor.get("locations", [])]
            geo_lower = geography.lower()
            geo_score = 10.0 if any(geo_lower in loc for loc in locations) else 0.0

            # ── Frequency normalized (0-10) ───────────────────────────────
            freq = sponsor.get("frequency", 1)
            freq_score = min(10.0, (freq / max(max_frequency, 1)) * 10.0)

            # ── Spend proxy normalized (0-10) ─────────────────────────────
            # Check enrichment for spend mentions
            spend_score = 0.0
            if enrichment_text:
                spend_keywords = ["million", "sponsor", "partner", "invest", "budget"]
                matches = sum(1 for kw in spend_keywords if kw in enrichment_text.lower())
                spend_score = min(10.0, matches * 2.5)

            # ── Weighted composite ────────────────────────────────────────
            composite = (
                _W_INDUSTRY * industry_score
                + _W_GEO * geo_score
                + _W_FREQUENCY * freq_score
                + _W_SPEND * spend_score
            )
            # Normalize to 0-10
            sponsor["relevance_score"] = round(min(10.0, composite), 2)
            sponsor["score_breakdown"] = {
                "industry": round(industry_score, 2),
                "geography": round(geo_score, 2),
                "frequency": round(freq_score, 2),
                "spend_proxy": round(spend_score, 2),
            }

        return sponsors

    # ── Pass 5: Generate proposals ────────────────────────────────────────

    def _generate_proposals(
        self,
        sponsors: list[dict],
        cfg: Any,
        geography: str,
    ) -> dict[str, str]:
        """Generate markdown proposals for top 3 sponsors."""
        metadata: dict[str, str] = {}
        event_name = cfg.event_name or f"{cfg.category} Summit"

        for sponsor in sponsors[:_PROPOSAL_TOP]:
            name = sponsor["name"]
            # Generate proposal via LLM
            proposal_prompt = (
                f"Write a professional sponsorship proposal for {name} to sponsor "
                f"'{event_name}' in {geography}.\n\n"
                f"Event details:\n"
                f"- Category: {cfg.category}\n"
                f"- Expected attendance: {cfg.audience_size}\n"
                f"- Date: {cfg.event_dates}\n"
                f"- Sponsor relevance score: {sponsor.get('relevance_score', 'N/A')}/10\n"
                f"- Past sponsorship frequency: {sponsor.get('frequency', 1)} events\n\n"
                f"Include:\n"
                f"1. Title & executive summary\n"
                f"2. Proposed sponsorship tier (Gold/Silver/Bronze) based on score\n"
                f"3. Benefits package\n"
                f"4. ROI projections\n"
                f"5. Call to action\n\n"
                f"Output as formatted Markdown."
            )
            proposal_text = self._invoke_llm(proposal_prompt, temperature=0.4)

            # Try to save as PDF
            try:
                tier = "Gold" if sponsor.get("relevance_score", 0) >= 7 else (
                    "Silver" if sponsor.get("relevance_score", 0) >= 4 else "Bronze"
                )
                sponsor_schema = SponsorSchema(
                    name=name,
                    geo=geography,
                    tier=tier,
                    relevance_score=sponsor.get("relevance_score", 0),
                    industry=", ".join(sponsor.get("categories", [])),
                    website="",
                )
                safe_name = name.replace(" ", "_")
                output_path = f"output/proposals/{safe_name}_proposal.pdf"
                event_meta = {
                    "event_name": event_name,
                    "city": geography,
                    "date": cfg.event_dates,
                    "audience_size": cfg.audience_size,
                }
                pdf_path = save_proposal(sponsor_schema, event_meta, output_path)
                metadata[f"proposal_{name}"] = pdf_path
                self._log_info(f"  Proposal saved: {safe_name}_proposal.pdf")
            except Exception as e:
                self._log_info(f"  PDF generation failed for {name}: {e}")
                metadata[f"proposal_{name}_md"] = proposal_text[:500]

        return metadata

    # ── Main run ──────────────────────────────────────────────────────────

    def run(self, state: AgentState) -> dict[str, Any]:
        """Execute the 5-pass sponsor discovery pipeline."""
        self._current_pass = 0
        self._log_info("Starting sponsor discovery run...")

        try:
            cfg = state["event_config"]
            category = cfg.category
            geography = cfg.geography
            past_events = state.get("past_events", [])

            # ── Pass 1: Extract from past_events ──────────────────────────
            with self._pass_context(
                "Pass 1: Extract sponsors from past_events", state,
                f"sponsors for {category} events in {geography}"
            ):
                sponsors = self._extract_sponsors(past_events)

            # If no sponsors from past_events, try Tavily discovery
            if not sponsors:
                self._log_info("No sponsors from past_events — doing direct Tavily search")
                results = self._tavily_search(
                    f"{category} conference sponsors {geography} 2025", max_results=5
                )
                for r in results:
                    combined = r.get("content", "")
                    # Use LLM to extract sponsor names
                    extract_prompt = (
                        f"From the following text, extract a list of company names "
                        f"that are sponsors of {category} events.\n\n"
                        f"Text: {combined[:2000]}\n\n"
                        f"Output ONLY a JSON list of strings. Example: [\"Company A\", \"Company B\"]"
                    )
                    names = self._invoke_llm_json(extract_prompt)
                    if names and isinstance(names, list):
                        for name in names:
                            if isinstance(name, str) and name.strip():
                                sponsors.append({
                                    "name": name.strip(),
                                    "frequency": 1,
                                    "locations": [geography],
                                    "categories": [category],
                                    "enrichment": {},
                                })

            # ── Pass 2: Tavily enrichment for top 20 ──────────────────────
            with self._pass_context(
                "Pass 2: Tavily enrichment", state,
                f"enriching top sponsors for {category}"
            ):
                sponsors = self._enrich_sponsors(sponsors, geography)

            # ── Pass 3: PredictHQ Entity Xref ──────────────────────────────
            with self._pass_context(
                "Pass 3: PredictHQ Entity Xref", state,
                f"cross-referencing sponsors for {category}"
            ):
                sponsors = self._phq_entity_xref(sponsors)

            # ── Pass 4: Score all sponsors ────────────────────────────────
            with self._pass_context(
                "Pass 4: Scoring", state,
                f"scoring sponsors for {category} in {geography}"
            ):
                max_freq = max((s.get("frequency", 1) for s in sponsors), default=1)
                sponsors = self._score_sponsors(sponsors, category, geography, max_freq)

                # Sort and keep top N
                sponsors.sort(key=lambda s: s.get("relevance_score", 0), reverse=True)
                sponsors = sponsors[:_TOP_N]

            # ── Pass 5: Generate proposals for top 3 ─────────────────────
            with self._pass_context(
                "Pass 5: Generate proposals", state,
                f"proposals for top sponsors"
            ):
                metadata = self._generate_proposals(sponsors, cfg, geography)

            # ── Build output SponsorSchema list ───────────────────────────
            sponsor_schemas = []
            for s in sponsors:
                score = s.get("relevance_score", 0)
                tier = "Gold" if score >= 7 else ("Silver" if score >= 4 else "Bronze")
                sponsor_schemas.append(SponsorSchema(
                    name=s["name"],
                    geo=geography,
                    tier=tier,
                    relevance_score=score,
                    industry=", ".join(s.get("categories", [])),
                    website="",
                ))

            # Write to memory
            docs = [f"Sponsor: {s.name} | Tier: {s.tier} | Score: {s.relevance_score}" for s in sponsor_schemas]
            meta = [{"name": s.name, "tier": s.tier, "score": s.relevance_score} for s in sponsor_schemas]
            self._write_memory(docs, meta, collection="sponsors")
            
            # Chat Agent Indexing Contract
            run_id = state.get("metadata", {}).get("run_id", "unknown")
            chat_docs = []
            chat_meta = []
            for s in sponsors:
                score = s.get("relevance_score", 0)
                freq = s.get("frequency", 1)
                md_preview = metadata.get(f"proposal_{s['name']}_md", "")[:200]
                text = (
                    f"{s['name']}. Industry: {category}. Geography: {geography}. "
                    f"Score: {score}. Seen at: {freq} events. Proposal summary: {md_preview}"
                )
                chat_docs.append(text)
                chat_meta.append({
                    "agent": "sponsor",
                    "run_id": run_id,
                    "geography": geography,
                    "category": category,
                })
            self.index_to_chroma(chat_docs, "chat_index", chat_meta)

            self._log_info(f"Completed — {len(sponsor_schemas)} sponsors ranked")

            return {
                "sponsors": sponsor_schemas,
                "metadata": metadata,
            }

        except Exception as exc:
            return self._log_error(state, f"SponsorAgent failed: {exc}")
