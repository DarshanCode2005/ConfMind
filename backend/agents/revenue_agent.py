"""
revenue_agent.py — Revenue calculation and what-if scenario generation.

Reads AgentState.pricing (from PricingAgent) and AgentState.sponsors (from SponsorAgent),
performs pure arithmetic to produce a revenue summary, and writes it to AgentState.revenue.

No LLM, no external API — this agent runs entirely from existing state.

Pipeline
--------
  1. ticket_revenue   = sum(tier.revenue for tier in state["pricing"])
  2. sponsor_revenue  = sum(_SPONSOR_VALUE[sponsor.tier] for sponsor in state["sponsors"])
  3. total_revenue    = ticket_revenue + sponsor_revenue
  4. profit           = total_revenue - event_config.budget_usd
  5. break_even_price = event_config.budget_usd / event_config.audience_size
  6. what_if_scenarios = ±20% ticket price variants

Usage
-----
    agent = RevenueAgent()
    updated_state = agent.run(state)
    print(updated_state["revenue"])
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate  # type: ignore[import-untyped]

from backend.models.schemas import AgentState, SponsorSchema, TicketTierSchema

from .base_agent import BaseAgent

# ── Sponsor tier → revenue value (USD) ────────────────────────────────────────

_SPONSOR_VALUE: dict[str, float] = {
    "Gold": 50_000.0,
    "Silver": 20_000.0,
    "Bronze": 5_000.0,
    "General": 0.0,
}

# What-if price multipliers (base ±20%)
_WHAT_IF_MULTIPLIERS: list[tuple[str, float]] = [
    ("-20%", 0.8),
    ("base", 1.0),
    ("+20%", 1.2),
]


# ── Private helpers ────────────────────────────────────────────────────────────


def _calc_ticket_revenue(pricing: list[TicketTierSchema]) -> float:
    """Sum the pre-computed revenue field across all ticket tiers.

    Args:
        pricing: List of TicketTierSchema objects produced by the PricingAgent.

    Returns:
        Total ticket revenue in USD.
    """
    return sum(tier.revenue for tier in pricing)


def _calc_sponsor_revenue(sponsors: list[SponsorSchema]) -> float:
    """Sum sponsor values based on tier using the fixed _SPONSOR_VALUE map.

    Unknown tier strings are treated as 0 (same as General).

    Args:
        sponsors: List of SponsorSchema objects produced by the SponsorAgent.

    Returns:
        Total sponsor revenue in USD.
    """
    return sum(_SPONSOR_VALUE.get(s.tier, 0.0) for s in sponsors)


def _calc_what_if(pricing: list[TicketTierSchema]) -> list[dict]:
    """Generate what-if scenarios by scaling each tier's price ±20%.

    For each multiplier, recalculates ticket revenue as:
        sum(tier.price * multiplier * tier.est_sales)

    Args:
        pricing: List of TicketTierSchema objects.

    Returns:
        A list of scenario dicts, each with 'label', 'base_price_multiplier',
        and 'estimated_ticket_revenue'.
    """
    scenarios: list[dict] = []
    for label, multiplier in _WHAT_IF_MULTIPLIERS:
        estimated = sum(tier.price * multiplier * tier.est_sales for tier in pricing)
        scenarios.append(
            {
                "label": label,
                "base_price_multiplier": multiplier,
                "estimated_ticket_revenue": round(estimated, 2),
            }
        )
    return scenarios


# ── Agent ──────────────────────────────────────────────────────────────────────


class RevenueAgent(BaseAgent):
    """Aggregates ticket and sponsor revenue, computes profit and break-even price.

    Sources (from AgentState — no external calls):
        state["pricing"]     -- list[TicketTierSchema] from PricingAgent
        state["sponsors"]    -- list[SponsorSchema]    from SponsorAgent
        state["event_config"]-- EventConfigInput       (budget_usd, audience_size)

    Output:
        state["revenue"] -- dict with the following keys:
            ticket_revenue, sponsor_revenue, total_revenue,
            profit, break_even_price, what_if_scenarios
    """

    name: str = "revenue_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        """Unused stub — RevenueAgent does not call an LLM.

        Required by BaseAgent's abstract interface.
        """
        return ChatPromptTemplate.from_messages(
            [("system", "Revenue agent — no LLM required."), ("human", "{input}")]
        )

    def run(self, state: AgentState) -> AgentState:
        """Calculate revenue, profit, and what-if scenarios; write to state.

        Args:
            state: The shared LangGraph AgentState. Reads ``pricing``,
                   ``sponsors``, and ``event_config``. Writes ``revenue``.

        Returns:
            Updated AgentState with ``revenue`` populated.
        """
        try:
            cfg = state["event_config"]
            pricing: list[TicketTierSchema] = state.get("pricing", [])  # type: ignore[assignment]
            sponsors: list[SponsorSchema] = state.get("sponsors", [])  # type: ignore[assignment]

            # ── 1. Revenue components ─────────────────────────────────────────
            ticket_revenue = _calc_ticket_revenue(pricing)
            sponsor_revenue = _calc_sponsor_revenue(sponsors)
            total_revenue = ticket_revenue + sponsor_revenue

            # ── 2. Profit + break-even ────────────────────────────────────────
            profit = total_revenue - cfg.budget_usd
            audience = cfg.audience_size if cfg.audience_size > 0 else 1
            break_even_price = cfg.budget_usd / audience

            # ── 3. What-if scenarios ──────────────────────────────────────────
            what_if = _calc_what_if(pricing)

            # ── 4. Write results ──────────────────────────────────────────────
            state["revenue"] = {
                "ticket_revenue": round(ticket_revenue, 2),
                "sponsor_revenue": round(sponsor_revenue, 2),
                "total_revenue": round(total_revenue, 2),
                "profit": round(profit, 2),
                "break_even_price": round(break_even_price, 2),
                "what_if_scenarios": what_if,
            }

        except Exception as exc:
            state = self._log_error(state, f"RevenueAgent failed: {exc}")

        return state
