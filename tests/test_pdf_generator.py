"""
test_pdf_generator.py — Unit tests for backend/tools/pdf_generator.py.

WeasyPrint is NOT mocked — it runs locally and produces actual PDF bytes.
This validates the Jinja2 template renders without errors and WeasyPrint can
convert it.  No external network calls are made.
"""

from __future__ import annotations

import os

import pytest

from backend.models.schemas import SponsorSchema
from backend.tools.pdf_generator import render_proposal, save_proposal


@pytest.fixture()
def event_meta() -> dict:
    return {
        "event_name": "AI Summit 2025",
        "city": "Berlin",
        "date": "2025-09-15",
        "country": "DE",
        "category": "AI",
        "audience_size": "800",
        "contact_email": "sponsors@aisummit.io",
    }


@pytest.fixture()
def gold_sponsor() -> SponsorSchema:
    return SponsorSchema(
        name="TechCorp",
        industry="AI",
        geo="Europe",
        tier="Gold",
        relevance_score=9.0,
    )


# ─────────────────────────────────────────────
# render_proposal
# ─────────────────────────────────────────────


def test_render_proposal_returns_bytes(gold_sponsor: SponsorSchema, event_meta: dict) -> None:
    pdf = render_proposal(gold_sponsor, event_meta)
    assert isinstance(pdf, bytes)


def test_render_proposal_starts_with_pdf_magic_bytes(
    gold_sponsor: SponsorSchema, event_meta: dict
) -> None:
    """PDF files always start with the magic bytes %PDF."""
    pdf = render_proposal(gold_sponsor, event_meta)
    assert pdf[:4] == b"%PDF"


def test_render_proposal_non_empty(gold_sponsor: SponsorSchema, event_meta: dict) -> None:
    pdf = render_proposal(gold_sponsor, event_meta)
    assert len(pdf) > 1024  # A real PDF is always > 1 KB


@pytest.mark.parametrize("tier", ["Gold", "Silver", "Bronze", "General"])
def test_render_proposal_all_tiers(tier: str, event_meta: dict) -> None:
    """All four tiers should render without raising exceptions."""
    sponsor = SponsorSchema(name="AcmeCo", tier=tier, relevance_score=5.0)
    pdf = render_proposal(sponsor, event_meta)
    assert pdf[:4] == b"%PDF"


# ─────────────────────────────────────────────
# save_proposal
# ─────────────────────────────────────────────


def test_save_proposal_writes_file(gold_sponsor: SponsorSchema, event_meta: dict, tmp_path) -> None:
    out = str(tmp_path / "proposal.pdf")
    returned_path = save_proposal(gold_sponsor, event_meta, out)
    assert os.path.isfile(returned_path)
    assert returned_path == str(tmp_path / "proposal.pdf")


def test_save_proposal_creates_parent_dirs(
    gold_sponsor: SponsorSchema, event_meta: dict, tmp_path
) -> None:
    nested_path = str(tmp_path / "deep" / "nested" / "proposal.pdf")
    save_proposal(gold_sponsor, event_meta, nested_path)
    assert os.path.isfile(nested_path)
