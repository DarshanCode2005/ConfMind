"""
pricing_model.py — Attendance predictor and ticket tier generator.

Uses scikit-learn LinearRegression trained on the historical event dataset
to predict attendance for a given event configuration, then generates three
standard ticket tiers (Early Bird / General / VIP) with revenue projections.

No external API calls.  All inference is local.

Public interface
────────────────
AttendancePredictor.train(df)                     -> None
AttendancePredictor.predict(event_type, …)        -> int
AttendancePredictor.generate_tiers(base_price)    -> list[TicketTierSchema]
AttendancePredictor.calculate_break_even(costs, tiers) -> float
AttendancePredictor.save(path)                    -> None
AttendancePredictor.load(path)                    -> AttendancePredictor  (classmethod)

Usage example
─────────────
    import pandas as pd
    from backend.models.pricing_model import AttendancePredictor

    df = pd.read_csv("dataset/events_2025_2026.csv")
    model = AttendancePredictor()
    model.train(df)
    predicted = model.predict("AI", 150.0, "Berlin", 500)
    tiers = model.generate_tiers(base_price=150.0)
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression  # type: ignore[import-untyped]
from sklearn.preprocessing import LabelEncoder  # type: ignore[import-untyped]

from backend.models.schemas import TicketTierSchema

# Tier split: Early Bird 40%, General 45%, VIP 15% of predicted attendance
_TIER_SPLITS = {"Early Bird": 0.40, "General": 0.45, "VIP": 0.15}
# Price multipliers relative to the base (general) price
_PRICE_MULTIPLIERS = {"Early Bird": 0.70, "General": 1.00, "VIP": 2.50}


class AttendancePredictor:
    """Linear regression model for predicting event attendance.

    Features used for training:
      - event_type  (label-encoded string)
      - ticket_price_general   (float, USD)
      - city        (label-encoded string)
      - size_hint   (expected audience capacity hint, int)

    Target: estimated_attendance (int)
    """

    def __init__(self) -> None:
        self._model: LinearRegression = LinearRegression()
        self._event_type_enc: LabelEncoder = LabelEncoder()
        self._city_enc: LabelEncoder = LabelEncoder()
        self._is_trained: bool = False

    # ── Training ──────────────────────────────────────────────────────────

    def train(self, df: pd.DataFrame) -> None:
        """Fit the model on a DataFrame from the event dataset.

        Required columns: category, ticket_price_general, city,
                          estimated_attendance.
        Optional column:  venue_capacity (used as size_hint; defaults to 500
                          if missing).
        """
        required = {"category", "ticket_price_general", "city", "estimated_attendance"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Training DataFrame is missing columns: {missing}")

        df = df.copy().dropna(subset=list(required))

        # Encode categoricals
        et_encoded = self._event_type_enc.fit_transform(df["category"].astype(str))
        city_encoded = self._city_enc.fit_transform(df["city"].astype(str))

        size_hint = (
            df["venue_capacity"].fillna(500).astype(float)
            if "venue_capacity" in df.columns
            else np.full(len(df), 500.0)
        )

        features = np.column_stack(
            [
                et_encoded,
                df["ticket_price_general"].astype(float),
                city_encoded,
                size_hint,
            ]
        )
        y = df["estimated_attendance"].astype(float)

        self._model.fit(features, y)
        self._is_trained = True

    # ── Inference ─────────────────────────────────────────────────────────

    def _encode_unseen(self, encoder: LabelEncoder, value: str) -> int:
        """Encode a value, mapping unseen labels to the last known class index."""
        try:
            return int(encoder.transform([value])[0])
        except ValueError:
            # Unseen label — use the median index as a neutral fallback
            return len(encoder.classes_) // 2  # type: ignore[arg-type]

    def predict(
        self,
        event_type: str,
        price: float,
        city: str,
        size_hint: int = 500,
    ) -> int:
        """Predict attendance for an event configuration.

        Args:
            event_type: Category string (e.g. "AI", "Web3").
            price:      General ticket price in USD.
            city:       City name (e.g. "Berlin").
            size_hint:  Expected venue capacity or audience size hint.

        Returns:
            Predicted attendance as a positive integer.

        Raises:
            RuntimeError: If called before train().
        """
        if not self._is_trained:
            raise RuntimeError("Call train() before predict().")

        et_enc = self._encode_unseen(self._event_type_enc, event_type)
        city_enc = self._encode_unseen(self._city_enc, city)
        features = np.array([[et_enc, float(price), city_enc, float(size_hint)]])
        raw = float(self._model.predict(features)[0])
        return max(1, round(raw))

    # ── Tier generation ───────────────────────────────────────────────────

    def generate_tiers(
        self,
        base_price: float,
        predicted_attendance: int | None = None,
    ) -> list[TicketTierSchema]:
        """Generate three ticket tiers based on a base (general) price.

        Args:
            base_price:            General admission price (USD).
            predicted_attendance:  Override total attendance; if None kept at 1000.

        Returns:
            List of three TicketTierSchema objects: Early Bird, General, VIP.
        """
        total = predicted_attendance if predicted_attendance is not None else 1_000
        tiers: list[TicketTierSchema] = []
        for name, split in _TIER_SPLITS.items():
            price = round(base_price * _PRICE_MULTIPLIERS[name], 2)
            est_sales = round(total * split)
            revenue = round(price * est_sales, 2)
            tiers.append(
                TicketTierSchema(name=name, price=price, est_sales=est_sales, revenue=revenue)
            )
        return tiers

    # ── Break-even ────────────────────────────────────────────────────────

    @staticmethod
    def calculate_break_even(
        total_costs: float,
        tiers: list[TicketTierSchema],
    ) -> float:
        """Calculate the General ticket price required to break even.

        Assumes the tier revenue split stays the same (40/45/15) and only
        the General price changes.  Returns the minimum General price (USD).

        Args:
            total_costs: Total event costs in USD.
            tiers:       Current tier list from generate_tiers().

        Returns:
            Break-even General ticket price (float), or 0.0 if tiers is empty.
        """
        if not tiers:
            return 0.0
        total_revenue = sum(t.revenue for t in tiers)
        if total_revenue == 0:
            return 0.0
        # Scale all prices proportionally
        scale_factor = total_costs / total_revenue
        general_tier = next((t for t in tiers if t.name == "General"), tiers[0])
        return round(general_tier.price * scale_factor, 2)

    # ── Persistence ───────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Serialise the trained model to a pickle file."""
        if not self._is_trained:
            raise RuntimeError("Cannot save an untrained model.")
        payload: dict[str, Any] = {
            "model": self._model,
            "event_type_enc": self._event_type_enc,
            "city_enc": self._city_enc,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(payload, f)

    @classmethod
    def load(cls, path: str) -> AttendancePredictor:
        """Load a previously saved model from a pickle file."""
        with open(path, "rb") as f:
            payload: dict[str, Any] = pickle.load(f)
        instance = cls()
        instance._model = payload["model"]
        instance._event_type_enc = payload["event_type_enc"]
        instance._city_enc = payload["city_enc"]
        instance._is_trained = True
        return instance
