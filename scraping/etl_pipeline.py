"""
etl_pipeline.py — Normalize raw scraped dicts into clean EventSchema records.

This module is the final stage of the data pipeline:
  raw dict (from ScrapeGraph-AI) → normalised EventSchema → CSV / JSON

Public interface
────────────────
normalize_date(date_str)               -> str          (ISO 8601)
normalize_price(price_str)             -> float        (USD)
normalize_country(raw)                 -> str          (ISO alpha-2 uppercase)
normalize_event(raw)                   -> EventSchema
deduplicate(records, key_fields)       -> list[dict]
save_to_csv(records, path)             -> None
save_to_json(records, path)            -> None

Usage example
─────────────
    from scraping.etl_pipeline import normalize_event, save_to_json

    raw = {"event_name": "AI Summit", "date": "Sep 15 2025", ...}
    event = normalize_event(raw)
    save_to_json([event.model_dump()], "dataset/events_2025_2026.json")
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from backend.models.schemas import EventSchema

# ─────────────────────────────────────────────
# Date normalisation
# ─────────────────────────────────────────────

_DATE_FORMATS = [
    "%Y-%m-%d",  # ISO: 2025-09-15
    "%d/%m/%Y",  # European: 15/09/2025
    "%m/%d/%Y",  # US: 09/15/2025
    "%B %d, %Y",  # "September 15, 2025"
    "%b %d, %Y",  # "Sep 15, 2025"
    "%d %B %Y",  # "15 September 2025"
    "%d %b %Y",  # "15 Sep 2025"
    "%Y/%m/%d",  # "2025/09/15"
]


def normalize_date(date_str: str) -> str:
    """Convert a date string in any common format to ISO 8601 (YYYY-MM-DD).

    Returns the original string unchanged if no format matches, so the
    pipeline never silently drops data.
    """
    if not date_str or not isinstance(date_str, str):
        return ""
    date_str = date_str.strip()
    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    for fmt in _DATE_FORMATS:
        try:
            from datetime import datetime

            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str  # return as-is if unparseable


# ─────────────────────────────────────────────
# Price normalisation
# ─────────────────────────────────────────────

# Extremely simple conversion rates (good enough for MVP dataset)
_CURRENCY_APPROX: dict[str, float] = {
    "£": 1.27,  # GBP -> USD
    "€": 1.08,  # EUR -> USD
    "₹": 0.012,  # INR -> USD
    "sgd": 0.74,
    "aud": 0.65,
    "cad": 0.73,
}


def normalize_price(price_str: str) -> float:
    """Convert a price string to a USD float.

    Handles: "$1,500", "Free", "£200", "€150", "₹5000", "USD 200", "0".
    Returns 0.0 for free / missing values.
    """
    if not price_str or not isinstance(price_str, str):
        return 0.0
    s = price_str.strip().lower()
    if s in {"free", "0", "", "tba", "tbd", "n/a"}:
        return 0.0

    multiplier = 1.0
    for symbol, rate in _CURRENCY_APPROX.items():
        if symbol in s:
            multiplier = rate
            s = s.replace(symbol, "")
            break

    # Remove currency labels like "usd", "inr" etc.
    s = re.sub(r"[a-z]+", "", s)
    # Remove commas, $, spaces
    s = re.sub(r"[$, ]", "", s)
    # Take the first number if a range like "100-200" is given
    match = re.search(r"[\d.]+", s)
    if not match:
        return 0.0
    return round(float(match.group()) * multiplier, 2)


# ─────────────────────────────────────────────
# Country normalisation
# ─────────────────────────────────────────────

# Partial map of common country names scrapers might return -> ISO alpha-2
_COUNTRY_NAME_MAP: dict[str, str] = {
    "united states": "US",
    "usa": "US",
    "us": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "india": "IN",
    "singapore": "SG",
    "germany": "DE",
    "france": "FR",
    "australia": "AU",
    "canada": "CA",
    "japan": "JP",
    "netherlands": "NL",
    "spain": "ES",
    "italy": "IT",
    "brazil": "BR",
    "uae": "AE",
    "united arab emirates": "AE",
}


def normalize_country(raw: str) -> str:
    """Normalise a country name / code to uppercase ISO 3166-1 alpha-2.

    Always returns a string.  If unrecognised, returns the original (uppercased)
    so data is never silently dropped.
    """
    if not raw or not isinstance(raw, str):
        return ""
    cleaned = raw.strip().lower()
    # Check the name map first so aliases like "uk" -> "GB" take priority
    if cleaned in _COUNTRY_NAME_MAP:
        return _COUNTRY_NAME_MAP[cleaned]
    # Already a recognised 2-letter ISO code (but not in alias map)
    if re.match(r"^[a-z]{2}$", cleaned):
        return cleaned.upper()
    return raw.strip().upper()


# ─────────────────────────────────────────────
# Event normalisation
# ─────────────────────────────────────────────


def normalize_event(raw: dict[str, Any]) -> EventSchema:
    """Convert a raw scraped dict into a normalised EventSchema.

    String fields that look like prices are run through normalize_price.
    The date field runs through normalize_date.
    The country field runs through normalize_country.

    Unknown fields are silently ignored; EventSchema validates required fields.
    """
    cleaned: dict[str, Any] = {}

    cleaned["event_name"] = raw.get("event_name") or "Unnamed Event"
    cleaned["date"] = normalize_date(str(raw.get("date") or ""))
    cleaned["city"] = raw.get("city") or ""
    cleaned["country"] = normalize_country(str(raw.get("country") or ""))
    cleaned["category"] = raw.get("category") or ""
    cleaned["theme"] = raw.get("theme") or ""

    # Ensure lists are actually lists
    for list_field in ("sponsors", "speakers", "exhibitors"):
        val = raw.get(list_field)
        cleaned[list_field] = val if isinstance(val, list) else []

    cleaned["venue_name"] = raw.get("venue_name") or ""
    cleaned["source_url"] = raw.get("source_url") or ""

    for price_field in ("ticket_price_early", "ticket_price_general", "ticket_price_vip"):
        val = raw.get(price_field)
        if val is None or val == "":
            cleaned[price_field] = 0.0
        else:
            cleaned[price_field] = (
                normalize_price(str(val)) if isinstance(val, str) else float(val or 0)
            )

    attendance = raw.get("estimated_attendance")
    cleaned["estimated_attendance"] = (
        int(attendance) if attendance and str(attendance).isdigit() else 0
    )

    capacity = raw.get("venue_capacity")
    try:
        if capacity:
            val = int(capacity)
            cleaned["venue_capacity"] = val if val >= 1 else None
        else:
            cleaned["venue_capacity"] = None
    except (ValueError, TypeError):
        cleaned["venue_capacity"] = None

    return EventSchema(**cleaned)


# ─────────────────────────────────────────────
# Deduplication
# ─────────────────────────────────────────────


def deduplicate(
    records: list[dict[str, Any]],
    key_fields: list[str],
) -> list[dict[str, Any]]:
    """Remove duplicates from a list of dicts based on a composite key.

    The first occurrence of each unique key tuple is kept.

    Args:
        records:    List of raw dict records.
        key_fields: Field names that form the unique composite key.
                    e.g. ["event_name", "city"]
    """
    seen: set[tuple] = set()
    unique: list[dict[str, Any]] = []
    for record in records:
        key = tuple(record.get(f, "") for f in key_fields)
        if key not in seen:
            seen.add(key)
            unique.append(record)
    return unique


# ─────────────────────────────────────────────
# Serialisation helpers
# ─────────────────────────────────────────────


def save_to_csv(records: list[dict[str, Any]], path: str) -> None:
    """Write a list of record dicts to a CSV file.

    List-valued fields (sponsors, speakers, exhibitors) are serialised as
    pipe-separated strings so they survive CSV round-tripping.
    """
    flat: list[dict[str, Any]] = []
    for r in records:
        row = dict(r)
        for field in ("sponsors", "speakers", "exhibitors", "past_events"):
            if isinstance(row.get(field), list):
                row[field] = "|".join(str(x) for x in row[field])
        flat.append(row)
    df = pd.DataFrame(flat)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def save_to_json(records: list[dict[str, Any]], path: str) -> None:
    """Write a list of record dicts to a pretty-printed JSON file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False, default=str)
