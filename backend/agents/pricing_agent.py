"""
pricing_agent.py — Ticket pricing and attendance prediction agent for ConfMind.

Uses the AttendancePredictor (scikit-learn) to estimate audience size
and generate pricing tiers (Early Bird, General, VIP).
"""

from __future__ import annotations

import pandas as pd
from langchain_core.prompts import ChatPromptTemplate

from backend.models.pricing_model import AttendancePredictor
from backend.models.schemas import AgentState

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_DEFAULT_BASE_PRICE = 150.0  # fallback if no pricing metadata found
_DATASET_PATH = "dataset/events_2025_2026.csv"


class PricingAgent(BaseAgent):
    """Predicts attendance and generates ticket pricing tiers."""

    name: str = "pricing_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a pricing strategist for professional events. "
                    "You use historical data to project attendance and set optimal ticket prices.",
                ),
                ("human", "{input}"),
            ]
        )

    def run(self, state: AgentState) -> AgentState:
        try:
            cfg = state["event_config"]
            category = cfg.category
            city = cfg.geography
            audience_goal = cfg.audience_size

            # ── 1. Train model on local dataset ────────────────────────────────
            # In a production app you'd load a pre-trained model from a .pkl
            # but for this setup we fit on-the-fly.
            predictor = AttendancePredictor()
            df = pd.read_csv(_DATASET_PATH)
            predictor.train(df)

            # ── 2. Run prediction ──────────────────────────────────────────────
            # We predict using the audience goal as the 'size_hint'
            predicted_count = predictor.predict(
                event_type=category,
                price=_DEFAULT_BASE_PRICE,
                city=city,
                size_hint=audience_goal
            )

            # ── 3. Generate tiers ──────────────────────────────────────────────
            tiers = predictor.generate_tiers(
                base_price=_DEFAULT_BASE_PRICE,
                predicted_attendance=predicted_count
            )

            # ── 4. Write results ──────────────────────────────────────────────
            state["pricing"] = tiers
            
            # Save prediction to metadata for later agents
            metadata = dict(state.get("metadata", {}))
            # ── 3. Write results ──────────────────────────────────────────────
            return {"pricing": tiers}

        except Exception as exc:
            return self._log_error({}, f"PricingAgent failed: {exc}")
