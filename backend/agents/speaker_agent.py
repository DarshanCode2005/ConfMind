"""
speaker_agent.py — Speaker discovery and ranking agent for ConfMind.

Fetches speaker candidates from ScrapeGraph-AI and Serper, 
enriches them with LinkedIn data to calculate influence scores,
and writes the results to AgentState.
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState, SpeakerSchema
from backend.tools.linkedin_tool import enrich_speakers
from backend.tools.scraper_tool import search_speakers_structured
from backend.tools.serper_tool import search_speakers

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_TOP_N = 10  # how many speakers to keep in state


class SpeakerAgent(BaseAgent):
    """Discovers, scores, and ranks conference speakers."""

    name: str = "speaker_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        """Minimal prompt satisfying the BaseAgent contract."""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a speaker discovery specialist for conference planning. "
                    "You identify high-influence speakers based on their LinkedIn presence and past experience.",
                ),
                ("human", "{input}"),
            ]
        )

    def run(self, state: AgentState) -> AgentState:
        """Fetch, enrich, and rank speakers.

        Args:
            state: The shared LangGraph AgentState. Reads ``event_config``.
                   Writes ``speakers``.

        Returns:
            Updated AgentState.
        """
        try:
            cfg = state["event_config"]
            topic = cfg.category
            region = cfg.geography

            # ── 1. Fetch from ScrapeGraph-AI ──────────────────────────────────
            scraper_speakers: list[SpeakerSchema] = search_speakers_structured(topic, region)

            # ── 2. Fetch from Serper + merge (dedup by name) ──────────────────
            serper_results = search_speakers(topic, region)
            seen_names: set[str] = {s.name.lower() for s in scraper_speakers}
            for result in serper_results:
                name = result.title.strip()
                if name.lower() not in seen_names:
                    scraper_speakers.append(SpeakerSchema(name=name, region=region))
                    seen_names.add(name.lower())

            # ── 3. Enrich with LinkedIn (Influence Score) ─────────────────────
            # Note: enrich_speakers uses RAPIDAPI_KEY from env
            enriched = enrich_speakers(scraper_speakers)

            # ── 4. Sort + keep top N ──────────────────────────────────────────
            ranked = sorted(
                enriched,
                key=lambda s: s.influence_score,
                reverse=True,
            )[:_TOP_N]

            # ── 5. Write results ──────────────────────────────────────────────
            return {"speakers": ranked}

        except Exception as exc:
            return self._log_error({}, f"SpeakerAgent failed: {exc}")
