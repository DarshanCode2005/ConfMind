"""
test_revenue_agent.py — Unit tests for backend/agents/revenue_agent.py.

No external mocking needed — all logic is pure arithmetic on AgentState.
"""

from __future__ import annotations

import pytest

from backend.agents.revenue_agent import (
    RevenueAgent,
    _calc_sponsor_revenue,
    _calc_ticket_revenue,
    _calc_what_if,
)
from backend.models.schemas import (
    AgentState,
    EventConfigInput,
    SponsorSchema,
    TicketTierSchema,
)

# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────


def _make_state(
    pricing: list[TicketTierSchema] | None = None,
    sponsors: list[SponsorSchema] | None = None,
    budget_usd: float = 100_000.0,
    audience_size: int = 500,
) -> AgentState:
    return AgentState(
        event_config=EventConfigInput(
            category="AI",
            geography="Europe",
            audience_size=audience_size,
            budget_usd=budget_usd,
            event_dates="2025-09-15",
            event_name="AI Summit 2025",
        ),
        sponsors=sponsors or [],
        speakers=[],
        venues=[],
        exhibitors=[],
        pricing=pricing or [],
        communities=[],
        schedule=[],
        revenue={},
        gtm_messages={},
        messages=[],
        errors=[],
        metadata={},
    )


def _make_tier(
    name: str = "General", price: float = 100.0, est_sales: int = 200
) -> TicketTierSchema:
    return TicketTierSchema(name=name, price=price, est_sales=est_sales, revenue=price * est_sales)


def _make_sponsor(name: str = "Acme", tier: str = "Gold") -> SponsorSchema:
    return SponsorSchema(
        name=name,
        industry="Technology",
        geo="Europe",
        tier=tier,
        website="https://acme.com",
        relevance_score=8.0,
    )


# ─────────────────────────────────────────────
# Helper unit tests
# ─────────────────────────────────────────────


def test_calc_ticket_revenue_sums_tiers() -> None:
    """_calc_ticket_revenue must sum the pre-computed revenue field on each tier."""
    tiers = [
        _make_tier("Early Bird", price=50.0, est_sales=100),  # revenue = 5_000
        _make_tier("General", price=100.0, est_sales=300),  # revenue = 30_000
        _make_tier("VIP", price=500.0, est_sales=20),  # revenue = 10_000
    ]
    assert _calc_ticket_revenue(tiers) == pytest.approx(45_000.0)


def test_calc_sponsor_revenue_by_tier() -> None:
    """_calc_sponsor_revenue must use the fixed tier-value map."""
    sponsors = [
        _make_sponsor("A", "Gold"),  # 50_000
        _make_sponsor("B", "Silver"),  # 20_000
        _make_sponsor("C", "Bronze"),  # 5_000
        _make_sponsor("D", "General"),  # 0
    ]
    assert _calc_sponsor_revenue(sponsors) == pytest.approx(75_000.0)


def test_calc_what_if_has_three_scenarios() -> None:
    """_calc_what_if must return exactly 3 scenarios."""
    tiers = [_make_tier()]
    result = _calc_what_if(tiers)
    assert len(result) == 3


def test_calc_what_if_base_matches_tier_price() -> None:
    """The 'base' scenario (multiplier=1.0) must match the original ticket revenue."""
    tiers = [_make_tier("General", price=100.0, est_sales=200)]  # revenue = 20_000
    scenarios = _calc_what_if(tiers)
    base = next(s for s in scenarios if s["label"] == "base")
    assert base["estimated_ticket_revenue"] == pytest.approx(20_000.0)


# ─────────────────────────────────────────────
# RevenueAgent.run() tests
# ─────────────────────────────────────────────


def test_revenue_agent_run_returns_agent_state() -> None:
    """run() must return a dict containing the 'revenue' key."""
    result = RevenueAgent().run(_make_state())
    assert isinstance(result, dict)
    assert "revenue" in result


def test_revenue_agent_all_keys_present() -> None:
    """state['revenue'] must have all 6 required keys."""
    required = {
        "ticket_revenue",
        "sponsor_revenue",
        "total_revenue",
        "profit",
        "break_even_price",
        "what_if_scenarios",
    }
    result = RevenueAgent().run(_make_state())
    assert required.issubset(result["revenue"].keys())


def test_revenue_agent_total_is_ticket_plus_sponsor() -> None:
    """total_revenue must equal ticket_revenue + sponsor_revenue."""
    tiers = [_make_tier("General", price=100.0, est_sales=300)]  # 30_000
    sponsors = [_make_sponsor("A", "Gold")]  # 50_000

    result = RevenueAgent().run(_make_state(pricing=tiers, sponsors=sponsors))
    rev = result["revenue"]

    assert rev["total_revenue"] == pytest.approx(rev["ticket_revenue"] + rev["sponsor_revenue"])
    assert rev["total_revenue"] == pytest.approx(80_000.0)


def test_revenue_agent_profit_is_total_minus_budget() -> None:
    """profit must equal total_revenue - budget_usd."""
    tiers = [_make_tier("General", price=100.0, est_sales=500)]  # 50_000
    state = _make_state(pricing=tiers, budget_usd=100_000.0)

    result = RevenueAgent().run(state)
    rev = result["revenue"]

    assert rev["profit"] == pytest.approx(rev["total_revenue"] - 100_000.0)


def test_revenue_agent_break_even_price() -> None:
    """break_even_price must equal budget_usd / audience_size."""
    result = RevenueAgent().run(_make_state(budget_usd=100_000.0, audience_size=500))
    assert result["revenue"]["break_even_price"] == pytest.approx(200.0)


def test_revenue_agent_handles_empty_pricing_and_sponsors() -> None:
    """With no pricing tiers and no sponsors, all values should be 0 with no errors."""
    result = RevenueAgent().run(_make_state(pricing=[], sponsors=[]))
    rev = result["revenue"]

    assert rev["ticket_revenue"] == 0.0
    assert rev["sponsor_revenue"] == 0.0
    assert rev["total_revenue"] == 0.0
    assert result["errors"] == []
