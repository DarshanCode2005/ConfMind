"""
test_serper_tool.py — Unit tests for backend/tools/serper_tool.py.

All HTTP calls are mocked; no real Serper API key required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.models.schemas import SerperResult
from backend.tools.serper_tool import (
    SerperAPIError,
    _parse_results,
    search_communities,
    search_speakers,
    search_sponsors,
    search_venues,
    search_web,
)

# ─────────────────────────────────────────────
# Helpers / fixtures
# ─────────────────────────────────────────────


def _make_response(status: int, body: dict) -> MagicMock:
    """Build a fake requests.Response-like mock."""
    mock = MagicMock()
    mock.status_code = status
    mock.json.return_value = body
    mock.text = str(body)
    return mock


# ─────────────────────────────────────────────
# _parse_results
# ─────────────────────────────────────────────


def test_parse_results_returns_serper_result_objects(mock_serper_response: dict) -> None:
    results = _parse_results(mock_serper_response)
    assert len(results) == 2
    assert all(isinstance(r, SerperResult) for r in results)


def test_parse_results_position_starts_at_1(mock_serper_response: dict) -> None:
    results = _parse_results(mock_serper_response)
    assert results[0].position == 1
    assert results[1].position == 2


def test_parse_results_empty_organic() -> None:
    results = _parse_results({"organic": []})
    assert results == []


def test_parse_results_missing_snippet() -> None:
    raw = {"organic": [{"title": "T", "link": "https://x.com"}]}
    results = _parse_results(raw)
    assert results[0].snippet == ""


# ─────────────────────────────────────────────
# search_web
# ─────────────────────────────────────────────


def test_search_web_returns_list_of_results(mock_serper_response: dict) -> None:
    with patch("backend.tools.serper_tool.requests.post") as mock_post:
        mock_post.return_value = _make_response(200, mock_serper_response)
        results = search_web("test query", api_key="fake-key")

    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0].url == "https://techcorp.example.com"


def test_search_web_raises_on_non_200() -> None:
    with patch("backend.tools.serper_tool.requests.post") as mock_post:
        mock_post.return_value = _make_response(401, {"error": "Unauthorized"})
        with pytest.raises(SerperAPIError) as exc_info:
            search_web("query", api_key="bad-key")
    assert exc_info.value.status_code == 401


def test_search_web_missing_api_key_raises() -> None:
    with patch("backend.tools.serper_tool.os.getenv", return_value=""):
        with pytest.raises(EnvironmentError, match="SERPER_API_KEY"):
            search_web("query")


# ─────────────────────────────────────────────
# Convenience wrappers — query building
# ─────────────────────────────────────────────


def test_search_sponsors_builds_correct_query(mock_serper_response: dict) -> None:
    with patch("backend.tools.serper_tool.requests.post") as mock_post:
        mock_post.return_value = _make_response(200, mock_serper_response)
        search_sponsors("AI", "Europe", year=2025, api_key="fake-key")

    call_args = mock_post.call_args
    payload = (
        call_args.kwargs.get("json") or call_args.args[1]
        if call_args.args
        else call_args.kwargs["json"]
    )
    assert "AI" in payload["q"]
    assert "Europe" in payload["q"]
    assert "2025" in payload["q"]


def test_search_speakers_builds_correct_query(mock_serper_response: dict) -> None:
    with patch("backend.tools.serper_tool.requests.post") as mock_post:
        mock_post.return_value = _make_response(200, mock_serper_response)
        search_speakers("Web3", "India", api_key="fake-key")

    payload = mock_post.call_args.kwargs["json"]
    assert "Web3" in payload["q"]
    assert "India" in payload["q"]


def test_search_venues_builds_correct_query(mock_serper_response: dict) -> None:
    with patch("backend.tools.serper_tool.requests.post") as mock_post:
        mock_post.return_value = _make_response(200, mock_serper_response)
        search_venues("Berlin", "tech", api_key="fake-key")

    payload = mock_post.call_args.kwargs["json"]
    assert "venues" in payload["q"].lower()
    assert "Berlin" in payload["q"]


def test_search_communities_includes_discord_keyword(mock_serper_response: dict) -> None:
    with patch("backend.tools.serper_tool.requests.post") as mock_post:
        mock_post.return_value = _make_response(200, mock_serper_response)
        search_communities("AI", api_key="fake-key")

    payload = mock_post.call_args.kwargs["json"]
    assert "Discord" in payload["q"] or "community" in payload["q"].lower()
