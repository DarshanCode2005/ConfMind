"""
test_sponsor_agent.py — Unit tests for backend/agents/sponsor_agent.py.

All external I/O (scraper, serper, pdf generator) is fully mocked.
No API keys or network access required.
"""

from __future__ import annotations

from unittest.mock import patch

from backend.agents.sponsor_agent import SponsorAgent, _score_sponsor
from backend.models.schemas import (
    AgentState,
    EventConfigInput,
    SerperResult,
    SponsorSchema,
)

# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────


def _make_state(
    category: str = "AI",
    geography: str = "Europe",
    audience_size: int = 500,
    budget_usd: float = 50_000.0,
) -> AgentState:
    """Return a minimal AgentState for testing."""
    return AgentState(
        event_config=EventConfigInput(
            category=category,
            geography=geography,
            audience_size=audience_size,
            budget_usd=budget_usd,
            event_dates="2025-09-15",
            event_name="AI Summit 2025",
        ),
        sponsors=[],
        speakers=[],
        venues=[],
        exhibitors=[],
        pricing=[],
        communities=[],
        schedule=[],
        revenue={},
        gtm_messages={},
        messages=[],
        errors=[],
        metadata={},
    )


def _make_sponsor(
    name: str = "TechCorp",
    industry: str = "AI",
    geo: str = "Europe",
    tier: str = "Gold",
) -> SponsorSchema:
    return SponsorSchema(name=name, industry=industry, geo=geo, tier=tier)


def _make_serper_result(title: str = "CloudInc", position: int = 1) -> SerperResult:
    return SerperResult(title=title, url="https://example.com", snippet="", position=position)


# ─────────────────────────────────────────────
# _score_sponsor unit tests
# ─────────────────────────────────────────────


def test_score_sponsor_full_match() -> None:
    """Gold sponsor with matching industry and geo should get max raw score (20)."""
    sponsor = _make_sponsor(industry="AI", geo="Europe", tier="Gold")
    score = _score_sponsor(sponsor, "AI", "Europe")
    assert score == 20.0


def test_score_sponsor_partial_industry_match() -> None:
    """Partial industry keyword match returns 5, not 10."""
    sponsor = _make_sponsor(industry="Machine Learning", geo="Europe", tier="Gold")
    # "ai" is NOT in "machine learning" as a substring — partial check via word split
    score = _score_sponsor(sponsor, "AI", "Europe")
    # category.split() = ["AI"]; none of its words appear in "machine learning"
    # so industry_score=2, geo_score=5, tier_bonus=5 → 12
    assert score == 12.0


def test_score_sponsor_no_geo_match() -> None:
    """Geo mismatch yields 0 out of 5 for geo_score."""
    sponsor = _make_sponsor(industry="AI", geo="USA", tier="Silver")
    score = _score_sponsor(sponsor, "AI", "Europe")
    # industry=10, geo=0, tier=3 → 13
    assert score == 13.0


def test_score_sponsor_general_tier() -> None:
    """General tier contributes 0 to the score."""
    sponsor = _make_sponsor(industry="AI", geo="Europe", tier="General")
    score = _score_sponsor(sponsor, "AI", "Europe")
    # industry=10, geo=5, tier=0 → 15
    assert score == 15.0


# ─────────────────────────────────────────────
# SponsorAgent.run() tests
# ─────────────────────────────────────────────

_SCRAPER_RESULT = [
    _make_sponsor("TechCorp", industry="AI", geo="Europe", tier="Gold"),
    _make_sponsor("CloudInc", industry="Cloud", geo="USA", tier="Silver"),
]

_SERPER_RESULT = [
    _make_serper_result("NewSponsor"),
]


@patch("backend.agents.sponsor_agent.save_proposal", return_value="/tmp/fake.pdf")
@patch("backend.agents.sponsor_agent.search_sponsors", return_value=_SERPER_RESULT)
@patch("backend.agents.sponsor_agent.search_sponsors_structured", return_value=_SCRAPER_RESULT)
def test_sponsor_agent_run_returns_agent_state(mock_scraper, mock_serper, mock_pdf) -> None:
    """run() must return a dict containing the 'sponsors' key."""
    state = _make_state()
    result = SponsorAgent().run(state)

    assert isinstance(result, dict)
    assert "sponsors" in result


@patch("backend.agents.sponsor_agent.save_proposal", return_value="/tmp/fake.pdf")
@patch("backend.agents.sponsor_agent.search_sponsors", return_value=[])
@patch("backend.agents.sponsor_agent.search_sponsors_structured", return_value=_SCRAPER_RESULT)
def test_sponsor_agent_sponsors_are_sorted_by_score(mock_scraper, mock_serper, mock_pdf) -> None:
    """Sponsors must be sorted in descending relevance_score order."""
    state = _make_state()
    result = SponsorAgent().run(state)

    sponsors = result["sponsors"]
    assert len(sponsors) >= 2
    scores = [s.relevance_score for s in sponsors]
    assert scores == sorted(scores, reverse=True)


@patch("backend.agents.sponsor_agent.save_proposal", return_value="/tmp/fake.pdf")
@patch(
    "backend.agents.sponsor_agent.search_sponsors",
    return_value=[_make_serper_result("TechCorp")],  # same name as scraper result
)
@patch("backend.agents.sponsor_agent.search_sponsors_structured", return_value=_SCRAPER_RESULT)
def test_sponsor_agent_deduplicates_serper_and_scraper_results(
    mock_scraper, mock_serper, mock_pdf
) -> None:
    """'TechCorp' appears in both sources — should not be duplicated in output."""
    state = _make_state()
    result = SponsorAgent().run(state)

    names = [s.name for s in result["sponsors"]]
    assert names.count("TechCorp") == 1


@patch("backend.agents.sponsor_agent.save_proposal", return_value="/tmp/fake.pdf")
@patch("backend.agents.sponsor_agent.search_sponsors", return_value=[])
@patch("backend.agents.sponsor_agent.search_sponsors_structured", return_value=_SCRAPER_RESULT)
def test_sponsor_agent_saves_proposals_for_top_3(mock_scraper, mock_serper, mock_pdf) -> None:
    """save_proposal should be called at most 3 times (or len(sponsors) if fewer)."""
    state = _make_state()
    SponsorAgent().run(state)

    expected_calls = min(3, len(_SCRAPER_RESULT))
    assert mock_pdf.call_count == expected_calls


@patch("backend.agents.sponsor_agent.save_proposal", return_value="/tmp/fake.pdf")
@patch("backend.agents.sponsor_agent.search_sponsors", return_value=[])
@patch("backend.agents.sponsor_agent.search_sponsors_structured", return_value=_SCRAPER_RESULT)
def test_sponsor_agent_proposal_paths_stored_in_metadata(
    mock_scraper, mock_serper, mock_pdf
) -> None:
    """Proposal paths must be recorded in state['metadata'] under 'proposal_<name>' keys."""
    state = _make_state()
    result = SponsorAgent().run(state)

    proposal_keys = [k for k in result["metadata"] if k.startswith("proposal_")]
    assert len(proposal_keys) > 0
    assert all(result["metadata"][k] == "/tmp/fake.pdf" for k in proposal_keys)


@patch("backend.agents.sponsor_agent.save_proposal", return_value="/tmp/fake.pdf")
@patch("backend.agents.sponsor_agent.search_sponsors", return_value=[])
@patch("backend.agents.sponsor_agent.search_sponsors_structured", return_value=[])
def test_sponsor_agent_handles_empty_results(mock_scraper, mock_serper, mock_pdf) -> None:
    """When both tools return [], sponsors should be [] and no error logged."""
    state = _make_state()
    result = SponsorAgent().run(state)

    assert result["sponsors"] == []
    assert result["errors"] == []
    mock_pdf.assert_not_called()


@patch(
    "backend.agents.sponsor_agent.search_sponsors_structured",
    side_effect=RuntimeError("API is down"),
)
def test_sponsor_agent_logs_error_on_tool_exception(mock_scraper) -> None:
    """When a tool raises, _log_error must append to state['errors']."""
    state = _make_state()
    result = SponsorAgent().run(state)

    assert len(result["errors"]) == 1
    assert "SponsorAgent failed" in result["errors"][0]
    assert "API is down" in result["errors"][0]
