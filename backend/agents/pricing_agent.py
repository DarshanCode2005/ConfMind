"""
pricing_agent.py — Pricing & footfall agent for ConfMind.

Uses AttendancePredictor to estimate attendance and generate ticket tiers.
Output is written to state["pricing"] as list[TicketTierSchema].
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from langchain_core.prompts import ChatPromptTemplate  # type: ignore[import-untyped]

from backend.agents.base_agent import BaseAgent
from backend.models.pricing_model import AttendancePredictor
from backend.models.schemas import AgentState, EventConfigInput, TicketTierSchema


class PricingAgent(BaseAgent):
    """Estimate attendance and create ticket pricing tiers."""

    name = "pricing_agent"

    def __init__(self) -> None:
        self._predictor: AttendancePredictor | None = None

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a pricing analyst. Produce clear, realistic ticket tier plans.",
                ),
                ("human", "{input}"),
            ]
        )

    @staticmethod
    def _dataset_path() -> Path:
        return Path(__file__).resolve().parents[2] / "dataset" / "events_2025_2026.csv"

    @staticmethod
    def _pick_city(state: AgentState, cfg: EventConfigInput) -> str:
        venues = state.get("venues", [])
        if venues and venues[0].city:
            return venues[0].city
        return cfg.geography

    @staticmethod
    def _pick_size_hint(state: AgentState, cfg: EventConfigInput) -> int:
        venues = state.get("venues", [])
        if venues and venues[0].capacity is not None:
            return max(1, int(venues[0].capacity))
        return max(1, int(cfg.audience_size))

    @staticmethod
    def _derive_base_price(cfg: EventConfigInput, reference_price: float) -> float:
        """Blend historical price with budget-per-seat signal."""
        budget_signal = (cfg.budget_usd * 0.35) / max(1, cfg.audience_size)
        base = (0.7 * reference_price) + (0.3 * budget_signal)
        return round(max(10.0, base), 2)

    @staticmethod
    def _reference_price(df: pd.DataFrame, category: str, fallback: float = 100.0) -> float:
        subset = df[df["category"].astype(str) == str(category)]
        if subset.empty:
            series = df["ticket_price_general"]
        else:
            series = subset["ticket_price_general"]
        if series.empty:
            return fallback
        return float(series.astype(float).median())

    def _get_predictor(self) -> AttendancePredictor:
        if self._predictor is not None:
            return self._predictor

        model_path = os.getenv("ATTENDANCE_MODEL_PATH", "").strip()
        if model_path and Path(model_path).exists():
            self._predictor = AttendancePredictor.load(model_path)
            return self._predictor

        dataset_path = self._dataset_path()
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found at {dataset_path}")

        df = pd.read_csv(dataset_path)
        predictor = AttendancePredictor()
        predictor.train(df)

        if model_path:
            Path(model_path).parent.mkdir(parents=True, exist_ok=True)
            predictor.save(model_path)

        self._predictor = predictor
        return predictor

    def run(self, state: AgentState) -> AgentState:
        try:
            cfg = state["event_config"]
            predictor = self._get_predictor()
            df = pd.read_csv(self._dataset_path())

            city = self._pick_city(state, cfg)
            size_hint = self._pick_size_hint(state, cfg)
            reference_price = self._reference_price(df, cfg.category)
            base_price = self._derive_base_price(cfg, reference_price)

            predicted_attendance = predictor.predict(
                event_type=cfg.category,
                price=base_price,
                city=city,
                size_hint=size_hint,
            )
            tiers: list[TicketTierSchema] = predictor.generate_tiers(
                base_price=base_price,
                predicted_attendance=predicted_attendance,
            )
            break_even_price = predictor.calculate_break_even(cfg.budget_usd, tiers)
            conversion_rates = {
                tier.name: round(
                    (tier.est_sales / predicted_attendance) if predicted_attendance else 0.0,
                    4,
                )
                for tier in tiers
            }

            state["pricing"] = tiers
            metadata = dict(state.get("metadata", {}))
            metadata["pricing_summary"] = {
                "predicted_attendance": predicted_attendance,
                "optimal_ticket_pricing": {
                    "early_bird": next((t.price for t in tiers if t.name == "Early Bird"), 0.0),
                    "general": base_price,
                    "vip": next((t.price for t in tiers if t.name == "VIP"), 0.0),
                },
                "break_even_price": break_even_price,
                "city_used": city,
                "size_hint": size_hint,
                "total_est_revenue": round(sum(t.revenue for t in tiers), 2),
                "conversion_rates": conversion_rates,
            }
            state["metadata"] = metadata
        except Exception as exc:
            state = self._log_error(state, f"pricing_agent: {exc}")
        return state
