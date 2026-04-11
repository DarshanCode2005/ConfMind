"""
test_exhibitor_agent.py — Unit tests for backend/agents/exhibitor_agent.py.

All external I/O (scraper, LLM) is fully mocked.
No API keys or network access required.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from backend.agents.exhibitor_agent import (
    ExhibitorAgent,
    _format_exhibitor_list,
    _parse_llm_clusters,
)
from backend.models.schemas import (
    AgentState,
    EventConfigInput,
    ExhibitorSchema,
)

# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────


def _make_state(category: str = "AI", event_name: str = "AI Summit 2025") -> AgentState:
    return AgentState(
        event_config=EventConfigInput(
            category=category,
            geography="Europe",
            audience_size=500,
            budget_usd=50_000.0,
            event_dates="2025-09-15",
            event_name=event_name,
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


def _make_exhibitor(
    name: str = "Acme Corp",
    cluster: str = "",
    relevance: float = 0.0,
    website: str = "https://acme.com",
) -> ExhibitorSchema:
    return ExhibitorSchema(name=name, cluster=cluster, relevance=relevance, website=website)


_TWO_EXHIBITORS = [
    _make_exhibitor("Acme Corp"),
    _make_exhibitor("StartupXYZ", website=""),
]

_LLM_JSON = json.dumps(
    [
        {"cluster": "enterprise", "relevance": 8.5},
        {"cluster": "startup", "relevance": 6.0},
    ]
)


# ─────────────────────────────────────────────
# _format_exhibitor_list unit tests
# ─────────────────────────────────────────────


def test_format_exhibitor_list_numbered() -> None:
    """Output must be a numbered list with Name and Website fields."""
    result = _format_exhibitor_list(_TWO_EXHIBITORS)
    lines = result.strip().splitlines()
    assert lines[0].startswith("1.")
    assert "Acme Corp" in lines[0]
    assert lines[1].startswith("2.")
    assert "StartupXYZ" in lines[1]


def test_format_exhibitor_list_missing_website_shows_none() -> None:
    """Exhibitors without a website should show '(none)'."""
    result = _format_exhibitor_list([_make_exhibitor(website="")])
    assert "(none)" in result


# ─────────────────────────────────────────────
# _parse_llm_clusters unit tests
# ─────────────────────────────────────────────


def test_parse_llm_clusters_merges_correctly() -> None:
    """Valid JSON response should update cluster and relevance on each exhibitor."""
    result = _parse_llm_clusters(_LLM_JSON, _TWO_EXHIBITORS)
    assert result[0].cluster == "enterprise"
    assert result[0].relevance == 8.5
    assert result[1].cluster == "startup"
    assert result[1].relevance == 6.0


def test_parse_llm_clusters_falls_back_on_bad_json() -> None:
    """Invalid JSON response must return the original exhibitor list unchanged."""
    result = _parse_llm_clusters("this is not json", _TWO_EXHIBITORS)
    assert result[0].name == "Acme Corp"
    assert result[0].cluster == ""  # original value preserved
    assert result[0].relevance == 0.0


def test_parse_llm_clusters_clamps_relevance() -> None:
    """Relevance values outside [0, 10] must be clamped."""
    bad_json = json.dumps([{"cluster": "tools", "relevance": 99.0}])
    result = _parse_llm_clusters(bad_json, [_make_exhibitor()])
    assert result[0].relevance == 10.0


def test_parse_llm_clusters_rejects_invalid_cluster() -> None:
    """Unknown cluster values must fall back to the original cluster."""
    bad_json = json.dumps([{"cluster": "unknown_type", "relevance": 5.0}])
    original = _make_exhibitor(cluster="tools")
    result = _parse_llm_clusters(bad_json, [original])
    assert result[0].cluster == "tools"


# ─────────────────────────────────────────────
# ExhibitorAgent.run() tests
# ─────────────────────────────────────────────


@patch("backend.agents.exhibitor_agent.search_exhibitors_structured", return_value=_TWO_EXHIBITORS)
def test_exhibitor_agent_run_returns_agent_state(mock_scraper) -> None:
    """run() must return a dict containing the 'exhibitors' key."""
    agent = ExhibitorAgent()
    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(return_value=MagicMock(content=_LLM_JSON))
    agent._get_llm = MagicMock(return_value=mock_llm)

    result = agent.run(_make_state())

    assert isinstance(result, dict)
    assert "exhibitors" in result


@patch("backend.agents.exhibitor_agent.search_exhibitors_structured", return_value=_TWO_EXHIBITORS)
def test_exhibitor_agent_sorted_by_relevance(mock_scraper) -> None:
    """Output exhibitors must be sorted by relevance in descending order."""
    agent = ExhibitorAgent()
    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(return_value=MagicMock(content=_LLM_JSON))
    agent._get_llm = MagicMock(return_value=mock_llm)

    result = agent.run(_make_state())

    scores = [e.relevance for e in result["exhibitors"]]
    assert scores == sorted(scores, reverse=True)


@patch("backend.agents.exhibitor_agent.search_exhibitors_structured", return_value=_TWO_EXHIBITORS)
def test_exhibitor_agent_clusters_assigned(mock_scraper) -> None:
    """All returned exhibitors must have a valid cluster value."""
    valid = {"startup", "enterprise", "tools", "individual"}
    agent = ExhibitorAgent()
    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(return_value=MagicMock(content=_LLM_JSON))
    agent._get_llm = MagicMock(return_value=mock_llm)

    result = agent.run(_make_state())

    for ex in result["exhibitors"]:
        assert ex.cluster in valid


@patch("backend.agents.exhibitor_agent.search_exhibitors_structured", return_value=[])
def test_exhibitor_agent_handles_empty_scraper_result(mock_scraper) -> None:
    """When scraper returns [], exhibitors should be [] with no errors."""
    result = ExhibitorAgent().run(_make_state())

    assert result["exhibitors"] == []
    assert result["errors"] == []


@patch(
    "backend.agents.exhibitor_agent.search_exhibitors_structured",
    side_effect=RuntimeError("Scraper down"),
)
def test_exhibitor_agent_logs_error_on_scraper_exception(mock_scraper) -> None:
    """When the scraper raises, the error must be appended to state['errors']."""
    result = ExhibitorAgent().run(_make_state())

    assert len(result["errors"]) == 1
    assert "ExhibitorAgent failed" in result["errors"][0]
    assert "Scraper down" in result["errors"][0]
