"""
test_schemas.py — Pydantic v2 schema validation tests for backend/models/schemas.py.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.models.schemas import (
    EventSchema,
    ExhibitorSchema,
    SerperResult,
    SpeakerSchema,
    SponsorSchema,
    TicketTierSchema,
    VenueSchema,
)

# ─────────────────────────────────────────────
# SponsorSchema
# ─────────────────────────────────────────────


def test_sponsor_schema_valid() -> None:
    s = SponsorSchema(name="TechCorp", tier="Gold", relevance_score=8.5)
    assert s.name == "TechCorp"
    assert s.tier == "Gold"


def test_sponsor_schema_invalid_tier() -> None:
    with pytest.raises(ValidationError):
        SponsorSchema(name="X", tier="Platinum")


def test_sponsor_schema_score_out_of_range() -> None:
    with pytest.raises(ValidationError):
        SponsorSchema(name="X", relevance_score=11.0)


def test_sponsor_schema_negative_score() -> None:
    with pytest.raises(ValidationError):
        SponsorSchema(name="X", relevance_score=-1.0)


def test_sponsor_schema_missing_name() -> None:
    with pytest.raises(ValidationError):
        SponsorSchema(tier="Gold")  # type: ignore[call-arg]


# ─────────────────────────────────────────────
# SpeakerSchema
# ─────────────────────────────────────────────


def test_speaker_schema_valid() -> None:
    s = SpeakerSchema(name="Jane", influence_score=7.5)
    assert s.name == "Jane"
    assert s.influence_score == 7.5


def test_speaker_schema_negative_experience() -> None:
    with pytest.raises(ValidationError):
        SpeakerSchema(name="Jane", speaking_experience=-1)


def test_speaker_schema_score_exceeds_10() -> None:
    with pytest.raises(ValidationError):
        SpeakerSchema(name="Jane", influence_score=10.1)


# ─────────────────────────────────────────────
# VenueSchema
# ─────────────────────────────────────────────


def test_venue_schema_valid(sample_venue) -> None:
    assert sample_venue.capacity == 2000
    assert sample_venue.country == "DE"


def test_venue_schema_zero_capacity_invalid() -> None:
    with pytest.raises(ValidationError):
        VenueSchema(name="X", city="Y", capacity=0)


def test_venue_schema_none_capacity_is_allowed() -> None:
    v = VenueSchema(name="X", city="Y", capacity=None)
    assert v.capacity is None


# ─────────────────────────────────────────────
# TicketTierSchema
# ─────────────────────────────────────────────


def test_ticket_tier_valid_names() -> None:
    for name in ("Early Bird", "General", "VIP"):
        t = TicketTierSchema(name=name, price=100.0)
        assert t.name == name


def test_ticket_tier_invalid_name() -> None:
    with pytest.raises(ValidationError):
        TicketTierSchema(name="Premium", price=100.0)


def test_ticket_tier_negative_price() -> None:
    with pytest.raises(ValidationError):
        TicketTierSchema(name="General", price=-5.0)


def test_ticket_tier_default_revenue() -> None:
    t = TicketTierSchema(name="VIP", price=500.0)
    assert t.revenue == 0.0


# ─────────────────────────────────────────────
# EventSchema
# ─────────────────────────────────────────────


def test_event_schema_valid(sample_event) -> None:
    assert sample_event.event_name == "AI Summit 2025"
    assert isinstance(sample_event.sponsors, list)


def test_event_schema_missing_event_name() -> None:
    with pytest.raises(ValidationError):
        EventSchema()  # type: ignore[call-arg]


def test_event_schema_negative_attendance() -> None:
    with pytest.raises(ValidationError):
        EventSchema(event_name="X", estimated_attendance=-10)


# ─────────────────────────────────────────────
# SerperResult
# ─────────────────────────────────────────────


def test_serper_result_valid() -> None:
    r = SerperResult(title="T", url="https://x.com", position=1)
    assert r.position == 1


def test_serper_result_position_zero_invalid() -> None:
    with pytest.raises(ValidationError):
        SerperResult(title="T", url="https://x.com", position=0)


# ─────────────────────────────────────────────
# ExhibitorSchema
# ─────────────────────────────────────────────


def test_exhibitor_schema_valid(sample_exhibitor) -> None:
    assert sample_exhibitor.cluster == "startup"


def test_exhibitor_relevance_above_10_invalid() -> None:
    with pytest.raises(ValidationError):
        ExhibitorSchema(name="X", relevance=10.001)
