"""
speaker_agent.py — Speaker discovery, LinkedIn enrichment, and agenda topic mapping.

Fetches speaker candidates from ScrapeGraph-AI SearchGraph, enriches each speaker's
influence score via the LinkedIn RapidAPI, then uses an LLM to map each speaker to
a refined agenda topic aligned with the event theme.

Pipeline
--------
  1. search_speakers_structured(topic, region) -> list[SpeakerSchema]
  2. enrich_speakers(speakers)                 -> influence_score populated
  3. LLM per speaker: bio + existing topic -> refined agenda topic
  4. Sort descending by influence_score
  5. Write to AgentState.speakers

Usage
-----
    agent = SpeakerAgent()
    updated_state = agent.run(state)
    print(updated_state["speakers"])
"""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate  # type: ignore[import-untyped]

from backend.models.schemas import AgentState, SpeakerSchema
from backend.tools.linkedin_tool import enrich_speakers
from backend.tools.scraper_tool import search_speakers_structured

from .base_agent import BaseAgent

# ── Private helper ─────────────────────────────────────────────────────────────


def _map_topic(chain: Any, theme: str, speaker: SpeakerSchema) -> str:
    """Invoke the LLM chain and return a refined agenda topic string.

    Falls back to the speaker's existing topic on any exception so that a
    single LLM failure doesn't break the whole agent.

    Args:
        chain:   A compiled LangChain chain (prompt | llm).
        theme:   The event theme or name (e.g. "AI Summit 2025").
        speaker: The speaker whose topic is being refined.

    Returns:
        A refined topic string (max ~10 words), or the original topic on failure.
    """
    try:
        response = chain.invoke(
            {
                "theme": theme,
                "name": speaker.name,
                "bio": speaker.bio or "No bio available.",
                "topic": speaker.topic or "General",
            }
        )
        return response.content.strip()
    except Exception:  # non-fatal per-speaker failure — fall back to original topic
        return speaker.topic


# ── Agent ──────────────────────────────────────────────────────────────────────


class SpeakerAgent(BaseAgent):
    """Discovers, enriches, and ranks conference speakers.

    Sources:
        ScrapeGraph-AI SearchGraph -- returns structured SpeakerSchema objects

    Enrichment:
        LinkedIn RapidAPI via enrich_speakers() -- populates influence_score.
        Speakers without a linkedin_url are skipped gracefully (score stays 0.0).

    LLM usage:
        One ChatOpenAI call per speaker to map bio + existing topic to a refined
        agenda topic aligned with the event theme.

    Output:
        state["speakers"] -- sorted by influence_score descending
    """

    name: str = "speaker_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        """Return the topic-mapping prompt for this agent's LLM chain.

        The system message instructs the LLM to act as an agenda specialist and
        return ONLY the refined topic string -- no preamble or explanation.
        """
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a conference agenda specialist. "
                    "Given an event theme and a speaker's name, bio, and current topic, "
                    "return a single refined agenda topic (maximum 10 words) that best fits "
                    "the event theme. Respond with ONLY the topic string -- no explanation.",
                ),
                (
                    "human",
                    "Event theme: {theme}\nSpeaker: {name}\nBio: {bio}\nCurrent topic: {topic}",
                ),
            ]
        )

    def run(self, state: AgentState) -> AgentState:
        """Fetch, enrich, topic-map, and rank speakers; write to state.

        Args:
            state: The shared LangGraph AgentState.  Reads ``event_config``.
                   Writes ``speakers``.

        Returns:
            Updated AgentState with ``speakers`` populated.
        """
        try:
            cfg = state["event_config"]
            theme = cfg.event_name or f"{cfg.category} Summit"

            # ── 1. Fetch from ScrapeGraph-AI ──────────────────────────────────
            speakers: list[SpeakerSchema] = search_speakers_structured(cfg.category, cfg.geography)

            if not speakers:
                state["speakers"] = []
                return state

            # ── 2. LinkedIn enrichment ────────────────────────────────────────
            speakers = enrich_speakers(speakers)

            # ── 3. LLM topic mapping ──────────────────────────────────────────
            llm = self._get_llm(temperature=0.3)
            chain = self._build_prompt() | llm

            mapped: list[SpeakerSchema] = []
            for speaker in speakers:
                refined_topic = _map_topic(chain, theme, speaker)
                mapped.append(speaker.model_copy(update={"topic": refined_topic}))

            # ── 4. Sort by influence score ────────────────────────────────────
            ranked = sorted(mapped, key=lambda s: s.influence_score, reverse=True)

            # ── 5. Write results ──────────────────────────────────────────────
            state["speakers"] = ranked

        except Exception as exc:
            state = self._log_error(state, f"SpeakerAgent failed: {exc}")

        return state
