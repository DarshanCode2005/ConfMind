"""
revenue_agent.py — Revenue Aggregation Agent for ConfMind.

System Prompt:
  "You are the Revenue Agent. Aggregate only."

No tools. Compute totals, profit, ROI% from state.
"""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState

from .base_agent import BaseAgent

# ── Sponsor value assumptions ─────────────────────────────────────────────────

_SPONSOR_VALUES = {
    "Gold": 25000.0,
    "Silver": 10000.0,
    "Bronze": 5000.0,
    "General": 2000.0,
}
_EXHIBITOR_FEE = 2500.0  # Per exhibitor booth
_COMMUNITY_BONUS = 500.0  # Estimated per community channel contribution


class RevenueAgent(BaseAgent):
    """Pure aggregation agent — no external tools.

    Collects revenue projections from all other agents:
        1. Ticket revenue (from PricingAgent tiers)
        2. Sponsor revenue (from SponsorAgent tier assignments)
        3. Exhibitor revenue (from ExhibitorAgent count × booth fee)
        4. Community-driven estimates (optional uplift)

    Computes: total revenue, projected profit, ROI%, break-even status.

    Output:
        state["revenue"] — complete financial projection dict
    """

    name: str = "revenue_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are the Revenue Agent for ConfMind. You aggregate "
                    "financial data — you use NO external tools.\n\n"
                    "CRITICAL RULES:\n"
                    "1. Aggregate ONLY — do not generate new data.\n"
                    "2. Ticket revenue = sum(tier_price × estimated_sales) for all tiers.\n"
                    "3. Sponsor revenue = sum(sponsor_tier_value) for all sponsors.\n"
                    "4. Exhibitor revenue = exhibitor_count × booth_fee.\n"
                    "5. Profit = total_revenue - total_budget.\n"
                    "6. ROI% = (profit / budget) × 100.\n"
                    "7. Include break-even analysis if available from PricingAgent.\n"
                    "8. All values in USD, rounded to 2 decimal places.",
                ),
                ("human", "{input}"),
            ]
        )

    # ── Main run ──────────────────────────────────────────────────────────

    def run(self, state: AgentState) -> dict[str, Any]:
        """Aggregate all revenue streams. No tools."""
        self._current_pass = 0
        self._log_info("Starting revenue aggregation...")

        try:
            cfg = state["event_config"]
            budget = cfg.budget_usd

            # ── 1. Ticket Revenue ─────────────────────────────────────────
            with self._pass_context(
                "Aggregate: Ticket revenue", state, "ticket revenue from pricing"
            ):
                ticket_revenue = 0.0
                pricing = state.get("pricing", [])
                ticket_breakdown = []
                for tier in pricing:
                    tier_revenue = (
                        getattr(tier, "revenue", 0.0) if hasattr(tier, "revenue") else 0.0
                    )
                    tier_name = (
                        getattr(tier, "name", "Unknown") if hasattr(tier, "name") else "Unknown"
                    )
                    tier_price = getattr(tier, "price", 0.0) if hasattr(tier, "price") else 0.0
                    tier_sales = getattr(tier, "est_sales", 0) if hasattr(tier, "est_sales") else 0

                    ticket_revenue += tier_revenue
                    ticket_breakdown.append(
                        {
                            "tier": tier_name,
                            "price": round(tier_price, 2),
                            "estimated_sales": tier_sales,
                            "revenue": round(tier_revenue, 2),
                        }
                    )
                self._log_info(f"  Ticket revenue: ${ticket_revenue:,.2f}")

            # ── 2. Sponsor Revenue ────────────────────────────────────────
            with self._pass_context(
                "Aggregate: Sponsor revenue", state, "sponsor revenue from sponsors"
            ):
                sponsor_revenue = 0.0
                sponsor_breakdown = []
                for s in state.get("sponsors", []):
                    tier = getattr(s, "tier", "General") if hasattr(s, "tier") else "General"
                    name = getattr(s, "name", "Unknown") if hasattr(s, "name") else "Unknown"
                    value = _SPONSOR_VALUES.get(tier, 2000.0)
                    sponsor_revenue += value
                    sponsor_breakdown.append(
                        {
                            "sponsor": name,
                            "tier": tier,
                            "value": round(value, 2),
                        }
                    )
                self._log_info(
                    f"  Sponsor revenue: ${sponsor_revenue:,.2f} ({len(sponsor_breakdown)} sponsors)"
                )

            # ── 3. Exhibitor Revenue ──────────────────────────────────────
            with self._pass_context("Aggregate: Exhibitor revenue", state, "exhibitor revenue"):
                exhibitors = state.get("exhibitors", [])
                exhibitor_count = len(exhibitors)
                exhibitor_revenue = exhibitor_count * _EXHIBITOR_FEE
                self._log_info(
                    f"  Exhibitor revenue: ${exhibitor_revenue:,.2f} ({exhibitor_count} exhibitors)"
                )

            # ── 4. Community/GTM uplift (optional) ────────────────────────
            communities = state.get("communities", [])
            community_count = len(communities)
            community_uplift = community_count * _COMMUNITY_BONUS

            # ── 5. Total, Profit, ROI ─────────────────────────────────────
            total_revenue = ticket_revenue + sponsor_revenue + exhibitor_revenue + community_uplift
            projected_profit = total_revenue - budget
            roi_pct = round((projected_profit / budget) * 100, 2) if budget > 0 else 0.0

            # ── 6. Break-even status ──────────────────────────────────────
            pricing_analysis = state.get("metadata", {}).get("pricing_analysis", {})
            break_even = pricing_analysis.get("break_even", {})
            break_even_attendance = break_even.get("break_even_attendance", 0)

            # Monte Carlo data
            monte_carlo = pricing_analysis.get("monte_carlo", {})

            # ── 7. Build comprehensive output ─────────────────────────────
            projection = {
                "ticket_revenue": round(ticket_revenue, 2),
                "ticket_breakdown": ticket_breakdown,
                "sponsor_revenue": round(sponsor_revenue, 2),
                "sponsor_breakdown": sponsor_breakdown,
                "exhibitor_revenue": round(exhibitor_revenue, 2),
                "exhibitor_count": exhibitor_count,
                "community_uplift": round(community_uplift, 2),
                "community_count": community_count,
                "total_projected_revenue": round(total_revenue, 2),
                "budget_usd": round(budget, 2),
                "projected_profit": round(projected_profit, 2),
                "roi_percentage": roi_pct,
                "break_even": {
                    "attendance_needed": break_even_attendance,
                    "is_profitable": projected_profit > 0,
                    "profit_margin_pct": round((projected_profit / total_revenue) * 100, 2)
                    if total_revenue > 0
                    else 0.0,
                },
                "monte_carlo_summary": {
                    "revenue_p10": monte_carlo.get("revenue", {}).get("p10", 0),
                    "revenue_p50": monte_carlo.get("revenue", {}).get("p50", 0),
                    "revenue_p90": monte_carlo.get("revenue", {}).get("p90", 0),
                    "attendance_mean": monte_carlo.get("attendance", {}).get("mean", 0),
                },
                "sources": {
                    "pricing_tiers": len(ticket_breakdown),
                    "sponsors": len(sponsor_breakdown),
                    "exhibitors": exhibitor_count,
                    "communities": community_count,
                },
            }

            # Write to memory
            docs = [
                f"Revenue: Total ${total_revenue:,.2f} | "
                f"Profit ${projected_profit:,.2f} | ROI {roi_pct}%"
            ]
            meta = [{"total": total_revenue, "profit": projected_profit, "roi": roi_pct}]
            self._write_memory(docs, meta, collection="events")

            # Chat Agent Indexing Contract
            run_id = state.get("metadata", {}).get("run_id", "unknown")
            chat_docs = [
                f"Revenue Projection: Total revenue: ${total_revenue:,.2f}. "
                f"Ticket revenue: ${ticket_revenue:,.2f}. "
                f"Sponsor revenue: ${sponsor_revenue:,.2f}. "
                f"Exhibitor revenue: ${exhibitor_revenue:,.2f}. "
                f"Projected profit: ${projected_profit:,.2f}. ROI: {roi_pct}%."
            ]
            chat_meta = [{"agent": "revenue", "run_id": run_id}]

            self.index_to_chroma(chat_docs, "chat_index", chat_meta)

            self._log_info(
                f"Completed — Total: ${total_revenue:,.2f}, "
                f"Profit: ${projected_profit:,.2f}, ROI: {roi_pct}%"
            )

            return {"revenue": projection}

        except Exception as exc:
            return self._log_error(state, f"RevenueAgent failed: {exc}")
