"""Unit tests for backend/agents/pricing_agent.py."""

from __future__ import annotations

from backend.agents.pricing_agent import PricingAgent
from backend.models.schemas import EventConfigInput, TicketTierSchema, VenueSchema


def _base_state() -> dict:
    return {
        "event_config": EventConfigInput(
            category="AI",
            geography="Europe",
            audience_size=800,
            budget_usd=50_000,
            event_dates="2026-10-10",
            event_name="AI Summit",
        ),
        "sponsors": [],
        "speakers": [],
        "venues": [],
        "exhibitors": [],
        "pricing": [],
        "communities": [],
        "schedule": [],
        "revenue": {},
        "gtm_messages": {},
        "messages": [],
        "errors": [],
        "metadata": {},
    }


class _FakePredictor:
    def __init__(self) -> None:
        self.last_predict_args: dict | None = None

    def predict(self, event_type: str, price: float, city: str, size_hint: int = 500) -> int:
        self.last_predict_args = {
            "event_type": event_type,
            "price": price,
            "city": city,
            "size_hint": size_hint,
        }
        return 900

    def generate_tiers(
        self,
        base_price: float,
        predicted_attendance: int | None = None,
    ) -> list[TicketTierSchema]:
        del base_price
        del predicted_attendance
        return [
            TicketTierSchema(name="Early Bird", price=70.0, est_sales=360, revenue=25200.0),
            TicketTierSchema(name="General", price=100.0, est_sales=405, revenue=40500.0),
            TicketTierSchema(name="VIP", price=250.0, est_sales=135, revenue=33750.0),
        ]

    @staticmethod
    def calculate_break_even(total_costs: float, tiers: list[TicketTierSchema]) -> float:
        del total_costs
        del tiers
        return 96.75


def test_pricing_agent_sets_tiers_and_summary(monkeypatch) -> None:
    agent = PricingAgent()
    fake_predictor = _FakePredictor()

    monkeypatch.setattr(agent, "_get_predictor", lambda: fake_predictor)
    monkeypatch.setattr(agent, "_dataset_path", lambda: "unused.csv")
    monkeypatch.setattr(
        "backend.agents.pricing_agent.pd.read_csv",
        lambda _path: __import__("pandas").DataFrame(
            {
                "category": ["AI"],
                "ticket_price_general": [100.0],
                "city": ["Berlin"],
                "estimated_attendance": [800],
            }
        ),
    )

    state = _base_state()
    state["venues"] = [
        VenueSchema(
            name="Tech Hall",
            city="Berlin",
            country="DE",
            capacity=1200,
            source_url="https://example.com/venue",
        )
    ]

    result = agent.run(state)

    assert len(result["pricing"]) == 3
    assert result["errors"] == []
    summary = result["metadata"]["pricing_summary"]
    assert summary["predicted_attendance"] == 900
    assert summary["break_even_price"] == 96.75
    assert summary["city_used"] == "Berlin"
    assert summary["size_hint"] == 1200
    assert summary["optimal_ticket_pricing"]["general"] > 0
    assert summary["optimal_ticket_pricing"]["vip"] > summary["optimal_ticket_pricing"]["general"]
    assert summary["conversion_rates"]["Early Bird"] == 0.4
    assert summary["conversion_rates"]["General"] == 0.45
    assert summary["conversion_rates"]["VIP"] == 0.15
    assert fake_predictor.last_predict_args is not None
    assert fake_predictor.last_predict_args["city"] == "Berlin"
    assert fake_predictor.last_predict_args["size_hint"] == 1200


def test_pricing_agent_logs_errors(monkeypatch) -> None:
    agent = PricingAgent()
    monkeypatch.setattr(
        agent, "_get_predictor", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    state = _base_state()
    result = agent.run(state)

    assert result["pricing"] == []
    assert len(result["errors"]) == 1
    assert "pricing_agent" in result["errors"][0]
