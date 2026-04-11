"""
exhibitor_agent.py — Exhibitor discovery, LLM cluster assignment, and relevance scoring.

Fetches exhibitor candidates from ScrapeGraph-AI SearchGraph, then uses a single
batched LLM call to assign each exhibitor to a cluster and score its relevance to
the event theme. All exhibitors are sent in one prompt to minimise API calls.

Pipeline
--------
  1. search_exhibitors_structured(category) -> list[ExhibitorSchema]
  2. LLM batch call: assign cluster + relevance for all exhibitors at once
  3. _parse_llm_clusters(): merge JSON response back into schema list
  4. Sort descending by relevance
  5. Write to AgentState.exhibitors

Usage
-----
    agent = ExhibitorAgent()
    updated_state = agent.run(state)
    print(updated_state["exhibitors"])
"""

from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate  # type: ignore[import-untyped]

from backend.models.schemas import AgentState, ExhibitorSchema
from backend.tools.scraper_tool import search_exhibitors_structured

from .base_agent import BaseAgent

# ── Valid cluster labels ───────────────────────────────────────────────────────

_VALID_CLUSTERS = {"startup", "enterprise", "tools", "individual"}


# ── Private helpers ────────────────────────────────────────────────────────────


def _format_exhibitor_list(exhibitors: list[ExhibitorSchema]) -> str:
    """Format exhibitors as a numbered text block for the LLM prompt.

    Args:
        exhibitors: List of ExhibitorSchema objects to format.

    Returns:
        A numbered string like:
            1. Name: Acme Corp | Website: acme.com
            2. Name: StartupXYZ | Website: (none)
    """
    lines: list[str] = []
    for i, ex in enumerate(exhibitors, start=1):
        website = ex.website or "(none)"
        lines.append(f"{i}. Name: {ex.name} | Website: {website}")
    return "\n".join(lines)


def _parse_llm_clusters(
    response_text: str,
    exhibitors: list[ExhibitorSchema],
) -> list[ExhibitorSchema]:
    """Parse the LLM JSON response and merge cluster + relevance back into exhibitors.

    The LLM is expected to return a JSON array of objects, one per exhibitor,
    in the same order as the input.  Invalid JSON, missing keys, or out-of-range
    values fall back gracefully to the original schema values (non-fatal).

    Args:
        response_text: Raw string returned by the LLM (should be a JSON array).
        exhibitors:    Original list of ExhibitorSchema objects, same order as prompt.

    Returns:
        A new list of ExhibitorSchema objects with cluster and relevance populated.
    """
    try:
        parsed: list[dict] = json.loads(response_text.strip())
    except (json.JSONDecodeError, ValueError):
        # Bad JSON — return originals unchanged
        return exhibitors

    result: list[ExhibitorSchema] = []
    for i, exhibitor in enumerate(exhibitors):
        try:
            item = parsed[i]
            cluster = str(item.get("cluster", exhibitor.cluster)).lower()
            if cluster not in _VALID_CLUSTERS:
                cluster = exhibitor.cluster  # fall back to original

            raw_relevance = float(item.get("relevance", exhibitor.relevance))
            relevance = round(min(max(raw_relevance, 0.0), 10.0), 2)

            result.append(exhibitor.model_copy(update={"cluster": cluster, "relevance": relevance}))
        except (IndexError, KeyError, TypeError, ValueError):
            # Keep original for this item, continue with the rest
            result.append(exhibitor)

    return result


# ── Agent ──────────────────────────────────────────────────────────────────────


class ExhibitorAgent(BaseAgent):
    """Discovers, clusters, and ranks conference exhibitors.

    Sources:
        ScrapeGraph-AI SearchGraph -- returns structured ExhibitorSchema objects.

    LLM usage:
        Single batched ChatOpenAI call for all exhibitors:
        assigns cluster (startup/enterprise/tools/individual) and relevance (0-10).
        Falls back to original values per-item on parse errors.

    Output:
        state["exhibitors"] -- sorted by relevance descending
    """

    name: str = "exhibitor_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        """Return the batched cluster-assignment prompt for this agent's LLM chain.

        The system message instructs the LLM to return a strict JSON array with
        no extra text so that _parse_llm_clusters() can parse it reliably.
        """
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a conference exhibitor analyst. "
                    "Given an event theme and a numbered list of exhibitors, "
                    "return a JSON array (same length and order as the input). "
                    "Each object must have exactly two keys:\n"
                    '  "cluster": one of startup, enterprise, tools, individual\n'
                    '  "relevance": a float from 0.0 to 10.0 based on fit to the event theme\n'
                    "Respond with ONLY the JSON array — no explanation, no markdown.",
                ),
                (
                    "human",
                    "Event theme: {theme}\n\nExhibitors:\n{exhibitor_list}",
                ),
            ]
        )

    def run(self, state: AgentState) -> AgentState:
        """Fetch, cluster, score, and rank exhibitors; write to state.

        Args:
            state: The shared LangGraph AgentState.  Reads ``event_config``.
                   Writes ``exhibitors``.

        Returns:
            Updated AgentState with ``exhibitors`` populated.
        """
        try:
            cfg = state["event_config"]
            theme = cfg.event_name or f"{cfg.category} Summit"

            # ── 1. Fetch from ScrapeGraph-AI ──────────────────────────────────
            exhibitors: list[ExhibitorSchema] = search_exhibitors_structured(cfg.category)

            if not exhibitors:
                state["exhibitors"] = []
                return state

            # ── 2. LLM batch: assign cluster + relevance ──────────────────────
            llm = self._get_llm(temperature=0.2)
            chain = self._build_prompt() | llm

            exhibitor_list_str = _format_exhibitor_list(exhibitors)
            response = chain.invoke({"theme": theme, "exhibitor_list": exhibitor_list_str})
            response_text: str = response.content.strip()

            # ── 3. Parse + merge ──────────────────────────────────────────────
            enriched = _parse_llm_clusters(response_text, exhibitors)

            # ── 4. Sort by relevance ──────────────────────────────────────────
            ranked = sorted(enriched, key=lambda e: e.relevance, reverse=True)

            # ── 5. Write results ──────────────────────────────────────────────
            state["exhibitors"] = ranked

        except Exception as exc:
            state = self._log_error(state, f"ExhibitorAgent failed: {exc}")

        return state
