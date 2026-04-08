"""
test_pricing_model.py — Unit tests for backend/models/pricing_model.py.

No external API calls.  Uses the sample_events_df fixture from conftest.py.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.models.pricing_model import AttendancePredictor
from backend.models.schemas import TicketTierSchema

# ─────────────────────────────────────────────
# train + predict
# ─────────────────────────────────────────────


def test_train_and_predict_returns_positive_int(sample_events_df: pd.DataFrame) -> None:
    model = AttendancePredictor()
    model.train(sample_events_df)
    result = model.predict("AI", 150.0, "Berlin", 500)
    assert isinstance(result, int)
    assert result >= 1


def test_predict_before_train_raises() -> None:
    model = AttendancePredictor()
    with pytest.raises(RuntimeError, match="train"):
        model.predict("AI", 150.0, "Berlin", 500)


def test_train_missing_columns_raises() -> None:
    bad_df = pd.DataFrame({"category": ["AI"], "city": ["Berlin"]})
    model = AttendancePredictor()
    with pytest.raises(ValueError, match="missing columns"):
        model.train(bad_df)


def test_predict_unseen_category_does_not_raise(sample_events_df: pd.DataFrame) -> None:
    """Unseen labels should fall back gracefully to a median index."""
    model = AttendancePredictor()
    model.train(sample_events_df)
    result = model.predict("QuantumComputing", 200.0, "Nowhere", 1000)
    assert result >= 1


# ─────────────────────────────────────────────
# generate_tiers
# ─────────────────────────────────────────────


def test_generate_tiers_returns_three_tiers(sample_events_df: pd.DataFrame) -> None:
    model = AttendancePredictor()
    model.train(sample_events_df)
    tiers = model.generate_tiers(base_price=100.0)
    assert len(tiers) == 3


def test_generate_tiers_names(sample_events_df: pd.DataFrame) -> None:
    model = AttendancePredictor()
    model.train(sample_events_df)
    tiers = model.generate_tiers(base_price=100.0)
    names = [t.name for t in tiers]
    assert "Early Bird" in names
    assert "General" in names
    assert "VIP" in names


def test_generate_tiers_vip_most_expensive(sample_events_df: pd.DataFrame) -> None:
    model = AttendancePredictor()
    model.train(sample_events_df)
    tiers = model.generate_tiers(base_price=100.0)
    tier_dict = {t.name: t for t in tiers}
    assert tier_dict["VIP"].price > tier_dict["General"].price > tier_dict["Early Bird"].price


def test_generate_tiers_revenue_positive(sample_events_df: pd.DataFrame) -> None:
    model = AttendancePredictor()
    model.train(sample_events_df)
    tiers = model.generate_tiers(base_price=100.0, predicted_attendance=1000)
    assert all(t.revenue > 0 for t in tiers)


def test_generate_tiers_without_training() -> None:
    """generate_tiers does not require a trained model — it only uses base_price."""
    model = AttendancePredictor()
    tiers = model.generate_tiers(base_price=200.0)
    assert len(tiers) == 3


# ─────────────────────────────────────────────
# calculate_break_even
# ─────────────────────────────────────────────


def test_calculate_break_even_returns_float() -> None:
    tiers = [
        TicketTierSchema(name="Early Bird", price=70.0, est_sales=400, revenue=28000.0),
        TicketTierSchema(name="General", price=100.0, est_sales=450, revenue=45000.0),
        TicketTierSchema(name="VIP", price=250.0, est_sales=150, revenue=37500.0),
    ]
    result = AttendancePredictor.calculate_break_even(100_000.0, tiers)
    assert isinstance(result, float)
    assert result > 0.0


def test_calculate_break_even_empty_tiers() -> None:
    result = AttendancePredictor.calculate_break_even(50_000.0, [])
    assert result == 0.0


def test_calculate_break_even_scales_correctly() -> None:
    """If current total revenue equals costs, break-even price == general price."""
    tiers = [
        TicketTierSchema(name="Early Bird", price=70.0, est_sales=400, revenue=28000.0),
        TicketTierSchema(name="General", price=100.0, est_sales=450, revenue=45000.0),
        TicketTierSchema(name="VIP", price=250.0, est_sales=150, revenue=37500.0),
    ]
    total_revenue = sum(t.revenue for t in tiers)  # 110_500
    result = AttendancePredictor.calculate_break_even(total_revenue, tiers)
    assert abs(result - 100.0) < 0.01  # Should equal the General price


# ─────────────────────────────────────────────
# save / load
# ─────────────────────────────────────────────


def test_save_and_load_round_trip(sample_events_df: pd.DataFrame, tmp_path) -> None:
    model = AttendancePredictor()
    model.train(sample_events_df)
    path = str(tmp_path / "model.pkl")
    model.save(path)

    loaded = AttendancePredictor.load(path)
    original_pred = model.predict("AI", 150.0, "Berlin", 500)
    loaded_pred = loaded.predict("AI", 150.0, "Berlin", 500)
    assert original_pred == loaded_pred


def test_save_untrained_model_raises(tmp_path) -> None:
    model = AttendancePredictor()
    with pytest.raises(RuntimeError, match="untrained"):
        model.save(str(tmp_path / "model.pkl"))
