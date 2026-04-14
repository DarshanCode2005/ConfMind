"""
sponsor_agent.py — Sponsor discovery and ranking agent for ConfMind.

Fetches sponsor candidates from two sources (ScrapeGraph-AI SearchGraph and
Serper Google Search), scores them with a deterministic rule-based formula,
generates PDF proposals for the top 3, and writes the result to AgentState.

Scoring formula (no LLM required)
──────────────────────────────────
  industry_relevance  0-10   keyword match between sponsor.industry and event category
  geo_match           0-5    exact region match between sponsor.geo and event geography
  tier_bonus          0-5    Gold=5, Silver=3, Bronze=1, General=0

Raw score (0-20) is normalised to 0-10 to stay within SponsorSchema bounds.

Usage
─────
    agent = SponsorAgent()
    updated_state = agent.run(state)
    print(updated_state["sponsors"])
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate  # type: ignore[import-untyped]

from backend.models.schemas import AgentState, SponsorSchema
from backend.tools.pdf_generator import save_proposal
from backend.tools.scraper_tool import search_sponsors_structured
from backend.tools.serper_tool import search_sponsors

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_TIER_BONUS: dict[str, float] = {
    "Gold": 5.0,
    "Silver": 3.0,
    "Bronze": 1.0,
    "General": 0.0,
}
_TOP_N = 10  # how many sponsors to keep in state
_PROPOSAL_TOP = 3  # how many PDF proposals to generate


# ── Private helper ─────────────────────────────────────────────────────────────


def _score_sponsor(sponsor: SponsorSchema, category: str, geography: str) -> float:
    """Return a *raw* score in [0, 20].  Normalise to [0, 10] before storing.

    Args:
        sponsor:   The sponsor to score.
        category:  Event category string (e.g. "AI", "Web3").
        geography: Target geography string (e.g. "Europe", "India").

    Returns:
        Raw score (float) in the range 0-20.
    """
    # Industry relevance (0-10)
    industry = sponsor.industry.lower()
    cat = category.lower()
    if industry and cat in industry:
        industry_score = 10.0
    elif industry and any(word in industry for word in cat.split()):
        industry_score = 5.0
    else:
        industry_score = 2.0

    # Geo match (0-5)
    geo_score = 5.0 if sponsor.geo.lower() == geography.lower() else 0.0

    # Tier bonus (0-5)
    tier_score = _TIER_BONUS.get(sponsor.tier, 0.0)

    return industry_score + geo_score + tier_score


# ── Agent ──────────────────────────────────────────────────────────────────────


class SponsorAgent(BaseAgent):
    """Discovers, scores, and ranks conference sponsors.

    Sources:
        1. ScrapeGraph-AI SearchGraph  — returns structured SponsorSchema objects
        2. Serper Google Search        — returns SerperResult hits converted to
                                         bare SponsorSchema stubs and merged in

    Output:
        state["sponsors"]  — top-N SponsorSchema list, sorted by relevance_score
        state["metadata"]  — proposal_<name> keys with absolute PDF paths for top 3
    """

    name: str = "sponsor_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        """Minimal prompt satisfying the BaseAgent abstract method contract.

        SponsorAgent does not call the LLM directly; scoring is rule-based.
        """
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a sponsor discovery specialist for conference planning. "
                    "You rank sponsors by industry relevance, geography match, and sponsorship tier.",
                ),
                ("human", "{input}"),
            ]
        )

    def run(self, state: AgentState) -> AgentState:
        """Fetch, score, and rank sponsors; generate proposals for top 3."""
        self._log_info("Starting sponsor discovery run...")
        try:
            cfg = state["event_config"]
            category = cfg.category
            geography = cfg.geography

            # ── 1. Fetch from ScrapeGraph-AI ──────────────────────────────────
            self._log_info(f"Querying SearchGraph for {category} sponsors in {geography}...")
            scraper_sponsors: list[SponsorSchema] = search_sponsors_structured(category, geography)
            self._log_info(f"Scraper found {len(scraper_sponsors)} sponsors.")

            # ── 2. Fetch from Serper + merge (dedup by name) ──────────────────
            self._log_info("Querying Serper for additional candidates...")
            serper_results = search_sponsors(category, geography)
            seen_names: set[str] = {s.name.lower() for s in scraper_sponsors}
            serper_count = 0
            for result in serper_results:
                name = result.title.strip()
                if name.lower() not in seen_names:
                    scraper_sponsors.append(SponsorSchema(name=name, geo=geography))
                    seen_names.add(name.lower())
                    serper_count += 1
            self._log_info(f"Added {serper_count} new candidates from Serper.")

            # ── 3. Score each sponsor ─────────────────────────────────────────
            self._log_info("Executing deterministic scoring formula...")
            for sponsor in scraper_sponsors:
                raw = _score_sponsor(sponsor, category, geography)
                # normalise 0-20 -> 0-10 to stay inside schema bounds
                sponsor.relevance_score = round(min(raw / 20.0 * 10.0, 10.0), 2)

            # ── 4. Sort + keep top N ──────────────────────────────────────────
            ranked = sorted(
                scraper_sponsors,
                key=lambda s: s.relevance_score,
                reverse=True,
            )[:_TOP_N]
            self._log_info(f"Ranking complete. Top sponsor: {ranked[0].name if ranked else 'N/A'}")

            # ── 5. PDF proposals for top 3 ────────────────────────────────────
            event_name = cfg.event_name or f"{category} Summit"
            event_meta = {
                "event_name": event_name,
                "city": geography,
                "date": cfg.event_dates,
                "audience_size": cfg.audience_size,
            }
            metadata: dict = dict(state.get("metadata", {}))

            self._log_info(f"Generating PDF proposals for top {_PROPOSAL_TOP} candidates...")
            for sponsor in ranked[:_PROPOSAL_TOP]:
                safe_name = sponsor.name.replace(" ", "_")
                output_path = f"output/proposals/{safe_name}_proposal.pdf"
                pdf_path = save_proposal(sponsor, event_meta, output_path)
                metadata[f"proposal_{sponsor.name}"] = pdf_path
                self._log_info(f"  - Proposal saved: {safe_name}_proposal.pdf")

            # ── 6. Write results ──────────────────────────────────────────────
            return {
                "sponsors": ranked,
                "metadata": metadata
            }

        except Exception as exc:
            # We must return the dictionary format that _log_error now produces
            return self._log_error({}, f"SponsorAgent failed: {exc}")
