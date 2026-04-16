"""
test_speaker_agent.py — Unit tests for backend/agents/speaker_agent.py.

All external I/O (scraper, LinkedIn, LLM) is fully mocked.
No API keys or network access required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.agents.speaker_agent import SpeakerAgent, _map_topic
from backend.models.schemas import (
    AgentState,
    EventConfigInput,
    SpeakerSchema,
)

# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────


def _make_state(
    category: str = "AI",
    geography: str = "Europe",
    event_name: str = "AI Summit 2025",
) -> AgentState:
    """Return a minimal AgentState for testing."""
    return AgentState(
        event_config=EventConfigInput(
            category=category,
            geography=geography,
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


def _make_speaker(
    name: str = "Jane Doe",
    influence_score: float = 7.5,
    topic: str = "Large Language Models",
    linkedin_url: str = "https://linkedin.com/in/janedoe",
) -> SpeakerSchema:
    return SpeakerSchema(
        name=name,
        bio="AI researcher and keynote speaker.",
        linkedin_url=linkedin_url,
        topic=topic,
        region="Europe",
        influence_score=influence_score,
    )


_TWO_SPEAKERS = [
    _make_speaker("Jane Doe", influence_score=7.5),
    _make_speaker("John Smith", influence_score=3.0, linkedin_url=""),
]

# ─────────────────────────────────────────────
# _map_topic unit tests
# ─────────────────────────────────────────────


def test_map_topic_returns_llm_content() -> None:
    """_map_topic should return the .content of the LLM response."""
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = MagicMock(content="  Generative AI in Production  ")
    speaker = _make_speaker()

    result = _map_topic(mock_chain, "AI Summit", speaker)

    assert result == "Generative AI in Production"


def test_map_topic_falls_back_on_exception() -> None:
    """_map_topic should return the original topic when the LLM raises."""
    mock_chain = MagicMock()
    mock_chain.invoke.side_effect = RuntimeError("LLM timeout")
    speaker = _make_speaker(topic="Original Topic")

    result = _map_topic(mock_chain, "AI Summit", speaker)

    assert result == "Original Topic"


# ─────────────────────────────────────────────
# SpeakerAgent.run() tests
# ─────────────────────────────────────────────


@patch("backend.agents.speaker_agent.enrich_speakers", return_value=_TWO_SPEAKERS)
@patch("backend.agents.speaker_agent.search_speakers_structured", return_value=_TWO_SPEAKERS)
def test_speaker_agent_run_returns_agent_state(mock_scraper, mock_enrich) -> None:
    """run() must return a dict containing the 'speakers' key."""
    agent = SpeakerAgent()
    # Mock the LLM so no real OpenAI call is made
    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(return_value=MagicMock(content="Mocked Topic"))
    agent._get_llm = MagicMock(return_value=mock_llm)

    result = agent.run(_make_state())

    assert isinstance(result, dict)
    assert "speakers" in result


@patch(
    "backend.agents.speaker_agent.enrich_speakers",
    return_value=[
        _make_speaker("High Influence", influence_score=9.0),
        _make_speaker("Low Influence", influence_score=2.0),
    ],
)
@patch("backend.agents.speaker_agent.search_speakers_structured", return_value=_TWO_SPEAKERS)
def test_speaker_agent_speakers_sorted_by_influence(mock_scraper, mock_enrich) -> None:
    """Output speakers must be sorted by influence_score descending."""
    agent = SpeakerAgent()
    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(return_value=MagicMock(content="Topic"))
    agent._get_llm = MagicMock(return_value=mock_llm)

    result = agent.run(_make_state())

    scores = [s.influence_score for s in result["speakers"]]
    assert scores == sorted(scores, reverse=True)


@patch("backend.agents.speaker_agent.enrich_speakers", return_value=_TWO_SPEAKERS)
@patch("backend.agents.speaker_agent.search_speakers_structured", return_value=_TWO_SPEAKERS)
def test_speaker_agent_enrich_speakers_called(mock_scraper, mock_enrich) -> None:
    """enrich_speakers must be called exactly once with the scraper output."""
    agent = SpeakerAgent()
    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(return_value=MagicMock(content="Topic"))
    agent._get_llm = MagicMock(return_value=mock_llm)

    agent.run(_make_state())

    mock_enrich.assert_called_once_with(_TWO_SPEAKERS)


@patch(
    "backend.agents.speaker_agent._map_topic",
    return_value="New Mapped Topic",
)
@patch(
    "backend.agents.speaker_agent.enrich_speakers",
    return_value=[_make_speaker(topic="Old Topic")],
)
@patch("backend.agents.speaker_agent.search_speakers_structured", return_value=_TWO_SPEAKERS)
def test_speaker_agent_topic_mapped_via_llm(mock_scraper, mock_enrich, mock_map) -> None:
    """Each speaker's topic should be updated to the value returned by _map_topic."""
    agent = SpeakerAgent()
    mock_llm = MagicMock()
    agent._get_llm = MagicMock(return_value=mock_llm)

    result = agent.run(_make_state())

    assert result["speakers"][0].topic == "New Mapped Topic"


@patch(
    "backend.agents.speaker_agent._map_topic",
    side_effect=RuntimeError("LLM down"),
)
@patch(
    "backend.agents.speaker_agent.enrich_speakers",
    return_value=[_make_speaker(topic="Original Topic")],
)
@patch("backend.agents.speaker_agent.search_speakers_structured", return_value=_TWO_SPEAKERS)
def test_speaker_agent_handles_llm_topic_failure(mock_scraper, mock_enrich, mock_map) -> None:
    """When _map_topic raises, the SpeakerAgent catches it at the outer try/except
    and records the error in state['errors']."""
    agent = SpeakerAgent()
    agent._get_llm = MagicMock(return_value=MagicMock())

    result = agent.run(_make_state())

    # Outer try/except catches it -> error logged
    assert len(result["errors"]) == 1
    assert "SpeakerAgent failed" in result["errors"][0]


@patch("backend.agents.speaker_agent.enrich_speakers", return_value=[])
@patch("backend.agents.speaker_agent.search_speakers_structured", return_value=[])
def test_speaker_agent_handles_empty_scraper_result(mock_scraper, mock_enrich) -> None:
    """When scraper returns [], speakers should be [] with no errors."""
    result = SpeakerAgent().run(_make_state())

    assert result["speakers"] == []
    assert result["errors"] == []


@patch(
    "backend.agents.speaker_agent.search_speakers_structured",
    side_effect=RuntimeError("Scraper is down"),
)
def test_speaker_agent_logs_error_on_scraper_exception(mock_scraper) -> None:
    """When the scraper raises, _log_error must append to state['errors']."""
    result = SpeakerAgent().run(_make_state())

    assert len(result["errors"]) == 1
    assert "SpeakerAgent failed" in result["errors"][0]
    assert "Scraper is down" in result["errors"][0]
