"""
revenue_agent.py — Financial projection agent for ConfMind.

Aggregates revenue from all sources:
1. Ticket sales (from pricing_agent)
2. Sponsorships (from sponsor_agent)
3. Exhibitor fees (from exhibitor_agent)
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState

from .base_agent import BaseAgent

# ── Price Assumptions ─────────────────────────────────────────────────────────

_SPONSOR_VALUES = {
    "Gold": 10000.0,
    "Silver": 5000.0,
    "Bronze": 2500.0,
    "General": 1000.0,
}
_EXHIBITOR_FEE = 1500.0


class RevenueAgent(BaseAgent):
    """Calculates total projected revenue and profit margins."""

    name: str = "revenue_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a financial analyst for conferences. "
                    "You aggregate revenue streams and calculate total financial projections.",
                ),
                ("human", "{input}"),
            ]
        )

    def run(self, state: AgentState) -> AgentState:
        try:
            # ── 1. Ticket Revenue ─────────────────────────────────────────────
            ticket_revenue = sum(tier.revenue for tier in state.get("pricing", []))

            # ── 2. Sponsor Revenue ────────────────────────────────────────────
            sponsor_revenue = 0.0
            for s in state.get("sponsors", []):
                sponsor_revenue += _SPONSOR_VALUES.get(s.tier, 1000.0)

            # ── 3. Exhibitor Revenue ──────────────────────────────────────────
            exhibitor_count = len(state.get("exhibitors", []))
            exhibitor_revenue = exhibitor_count * _EXHIBITOR_FEE

            # ── 4. Total and Net ──────────────────────────────────────────────
            total_revenue = ticket_revenue + sponsor_revenue + exhibitor_revenue
            budget = state["event_config"].budget_usd
            projected_profit = total_revenue - budget

            # ── 5. Build output ───────────────────────────────────────────────
            projection = {
                "ticket_revenue": round(ticket_revenue, 2),
                "sponsor_revenue": round(sponsor_revenue, 2),
                "exhibitor_revenue": round(exhibitor_revenue, 2),
                "total_projected_revenue": round(total_revenue, 2),
                "budget_usd": round(budget, 2),
                "projected_profit": round(projected_profit, 2),
                "roi_percentage": round((projected_profit / budget * 100), 2) if budget > 0 else 0.0,
            }
            # ── 4. Write results ──────────────────────────────────────────────
            return {"revenue": projection}

        except Exception as exc:
            return self._log_error({}, f"RevenueAgent failed: {exc}")
