"""
exhibitor_agent.py — Exhibitor discovery agent for ConfMind.

Fetches exhibitor candidates from ScrapeGraph-AI SearchGraph.
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState, ExhibitorSchema
from backend.tools.scraper_tool import search_exhibitors_structured

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_TOP_N = 10


class ExhibitorAgent(BaseAgent):
    """Discovers and ranks conference exhibitors."""

    name: str = "exhibitor_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an exhibitor discovery specialist. You find companies that would be "
                    "interested in exhibiting their products or services at a conference.",
                ),
                ("human", "{input}"),
            ]
        )

    def run(self, state: AgentState) -> AgentState:
        try:
            cfg = state["event_config"]
            category = cfg.category

            # ── 1. Fetch from ScrapeGraph-AI ──────────────────────────────────
            exhibitors: list[ExhibitorSchema] = search_exhibitors_structured(category)

            # ── 2. Sort + keep top N (ScrapeGraph might already score them) ────
            ranked = sorted(
                exhibitors,
                key=lambda e: e.relevance,
                reverse=True,
            )[:_TOP_N]

            # ── 3. Write results ──────────────────────────────────────────────
            return {"exhibitors": ranked}

        except Exception as exc:
            return self._log_error({}, f"ExhibitorAgent failed: {exc}")
