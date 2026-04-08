"""
test_etl_pipeline.py — Unit tests for scraping/etl_pipeline.py.

No external API calls.  All I/O uses pytest's tmp_path fixture.
"""

from __future__ import annotations

import json

import pytest

from scraping.etl_pipeline import (
    deduplicate,
    normalize_country,
    normalize_date,
    normalize_event,
    normalize_price,
    save_to_csv,
    save_to_json,
)

# ─────────────────────────────────────────────
# normalize_date
# ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        ("2025-09-15", "2025-09-15"),  # already ISO
        ("15/09/2025", "2025-09-15"),  # European DD/MM/YYYY
        ("09/15/2025", "2025-09-15"),  # US MM/DD/YYYY
        ("September 15, 2025", "2025-09-15"),  # long month name
        ("Sep 15, 2025", "2025-09-15"),  # short month name
        ("15 September 2025", "2025-09-15"),  # day-month-year
        ("", ""),  # empty string
    ],
)
def test_normalize_date(input_str: str, expected: str) -> None:
    assert normalize_date(input_str) == expected


def test_normalize_date_unparseable_returns_original() -> None:
    weird = "Quarter 3 2025"
    assert normalize_date(weird) == weird


# ─────────────────────────────────────────────
# normalize_price
# ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        ("$1,500", 1500.0),
        ("Free", 0.0),
        ("free", 0.0),
        ("0", 0.0),
        ("", 0.0),
        ("n/a", 0.0),
        ("£200", pytest.approx(254.0, abs=1.0)),  # GBP -> USD
        ("$99.99", 99.99),
        ("USD 300", 300.0),
        ("100-200", 100.0),  # range: take first number
    ],
)
def test_normalize_price(input_str: str, expected: float) -> None:
    assert normalize_price(input_str) == expected


# ─────────────────────────────────────────────
# normalize_country
# ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("India", "IN"),
        ("usa", "US"),
        ("United States", "US"),
        ("UK", "GB"),
        ("DE", "DE"),  # already ISO code (uppercase)
        ("de", "DE"),  # already ISO code (lowercase)
        ("Singapore", "SG"),
        ("", ""),
    ],
)
def test_normalize_country(raw: str, expected: str) -> None:
    assert normalize_country(raw) == expected


def test_normalize_country_unknown_returns_uppercase() -> None:
    result = normalize_country("Narnia")
    assert result == "NARNIA"


# ─────────────────────────────────────────────
# normalize_event
# ─────────────────────────────────────────────


def test_normalize_event_returns_event_schema() -> None:
    from backend.models.schemas import EventSchema

    raw = {
        "event_name": "AI Summit 2025",
        "date": "Sep 15, 2025",
        "city": "Berlin",
        "country": "Germany",
        "category": "AI",
        "ticket_price_general": "$149",
        "ticket_price_early": "$99",
        "ticket_price_vip": "$499",
        "estimated_attendance": "800",
        "venue_name": "Tech Center",
    }
    event = normalize_event(raw)
    assert isinstance(event, EventSchema)
    assert event.date == "2025-09-15"
    assert event.country == "DE"
    assert event.ticket_price_general == 149.0


def test_normalize_event_handles_missing_optional_fields() -> None:
    raw = {"event_name": "Minimal Event"}
    event = normalize_event(raw)
    assert event.event_name == "Minimal Event"
    assert event.ticket_price_general == 0.0
    assert event.estimated_attendance == 0
    assert event.venue_capacity is None


def test_normalize_event_list_fields_default_to_empty() -> None:
    event = normalize_event({"event_name": "Test"})
    assert event.sponsors == []
    assert event.speakers == []


# ─────────────────────────────────────────────
# deduplicate
# ─────────────────────────────────────────────


def test_deduplicate_removes_exact_duplicates() -> None:
    records = [
        {"event_name": "AI Summit", "city": "Berlin"},
        {"event_name": "AI Summit", "city": "Berlin"},  # duplicate
        {"event_name": "Web3 Conf", "city": "London"},
    ]
    unique = deduplicate(records, ["event_name", "city"])
    assert len(unique) == 2


def test_deduplicate_keeps_first_occurrence() -> None:
    records = [
        {"event_name": "X", "version": "v1"},
        {"event_name": "X", "version": "v2"},
    ]
    unique = deduplicate(records, ["event_name"])
    assert unique[0]["version"] == "v1"


def test_deduplicate_empty_list() -> None:
    assert deduplicate([], ["name"]) == []


# ─────────────────────────────────────────────
# save_to_json / save_to_csv
# ─────────────────────────────────────────────


def test_save_to_json_writes_valid_file(tmp_path) -> None:
    records = [{"event_name": "AI Summit", "city": "Berlin"}]
    path = str(tmp_path / "events.json")
    save_to_json(records, path)
    with open(path) as f:
        loaded = json.load(f)
    assert loaded[0]["event_name"] == "AI Summit"


def test_save_to_csv_writes_valid_file(tmp_path) -> None:
    import pandas as pd

    records = [
        {"event_name": "AI Summit", "city": "Berlin", "sponsors": ["TechCorp", "CloudInc"]},
    ]
    path = str(tmp_path / "events.csv")
    save_to_csv(records, path)
    df = pd.read_csv(path)
    assert df["event_name"][0] == "AI Summit"
    assert "TechCorp" in df["sponsors"][0]


def test_save_to_json_creates_parent_dirs(tmp_path) -> None:
    path = str(tmp_path / "subdir" / "deep" / "events.json")
    save_to_json([{"a": 1}], path)
    with open(path) as f:
        data = json.load(f)
    assert data[0]["a"] == 1
