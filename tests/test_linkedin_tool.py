"""
test_linkedin_tool.py — Unit tests for backend/tools/linkedin_tool.py.

RapidAPI is fully mocked; no real API key required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.models.schemas import LinkedInProfile, SpeakerSchema
from backend.tools.linkedin_tool import (
    LinkedInAPIError,
    LinkedInRateLimitError,
    calculate_influence_score,
    enrich_speakers,
    get_profile,
)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def _make_response(status: int, body: dict) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status
    mock.json.return_value = body
    mock.text = str(body)
    return mock


# ─────────────────────────────────────────────
# get_profile
# ─────────────────────────────────────────────


def test_get_profile_returns_linkedin_profile(
    mock_linkedin_api_response: dict,
    sample_linkedin_profile: LinkedInProfile,
) -> None:
    with patch("backend.tools.linkedin_tool.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, mock_linkedin_api_response)
        profile = get_profile("https://linkedin.com/in/janedoe", api_key="fake")

    assert isinstance(profile, LinkedInProfile)
    assert profile.name == "Jane Doe"
    assert profile.followers == 25000
    assert profile.connections == 500


def test_get_profile_raises_api_error_on_404() -> None:
    with patch("backend.tools.linkedin_tool.requests.get") as mock_get:
        mock_get.return_value = _make_response(404, {"error": "Not found"})
        with pytest.raises(LinkedInAPIError) as exc_info:
            get_profile("https://linkedin.com/in/nobody", api_key="fake")
    assert exc_info.value.status_code == 404


def test_get_profile_raises_rate_limit_after_retries() -> None:
    with (
        patch("backend.tools.linkedin_tool.requests.get") as mock_get,
        patch("backend.tools.linkedin_tool.time.sleep"),  # don't actually sleep in tests
    ):
        mock_get.return_value = _make_response(429, {"error": "Too many requests"})
        with pytest.raises(LinkedInRateLimitError):
            get_profile("https://linkedin.com/in/janedoe", api_key="fake")

    # Should have retried MAX_RETRIES times
    from backend.tools.linkedin_tool import MAX_RETRIES

    assert mock_get.call_count == MAX_RETRIES


def test_get_profile_missing_api_key_raises() -> None:
    with patch("backend.tools.linkedin_tool.os.getenv", return_value=""):
        with pytest.raises(EnvironmentError, match="RAPIDAPI_KEY"):
            get_profile("https://linkedin.com/in/janedoe")


# ─────────────────────────────────────────────
# calculate_influence_score
# ─────────────────────────────────────────────


def test_influence_score_is_between_0_and_10(sample_linkedin_profile: LinkedInProfile) -> None:
    score = calculate_influence_score(sample_linkedin_profile)
    assert 0.0 <= score <= 10.0


def test_influence_score_zero_followers() -> None:
    profile = LinkedInProfile(
        name="No Fame",
        followers=0,
        connections=0,
        recent_posts_count=0,
        linkedin_url="https://linkedin.com/in/nofame",
    )
    score = calculate_influence_score(profile)
    assert score == 0.0


def test_influence_score_is_deterministic(sample_linkedin_profile: LinkedInProfile) -> None:
    score1 = calculate_influence_score(sample_linkedin_profile)
    score2 = calculate_influence_score(sample_linkedin_profile)
    assert score1 == score2


def test_influence_score_high_follower_count_near_max() -> None:
    profile = LinkedInProfile(
        name="Famous Speaker",
        followers=100_000,
        connections=500,
        recent_posts_count=10,
        linkedin_url="https://linkedin.com/in/famous",
    )
    score = calculate_influence_score(profile)
    # Should be close to 10 but not exceed it
    assert score > 8.0
    assert score <= 10.0


# ─────────────────────────────────────────────
# enrich_speakers
# ─────────────────────────────────────────────


def test_enrich_speakers_adds_influence_score(
    sample_speaker: SpeakerSchema,
    mock_linkedin_api_response: dict,
) -> None:
    with patch("backend.tools.linkedin_tool.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, mock_linkedin_api_response)
        enriched = enrich_speakers([sample_speaker], api_key="fake")

    assert enriched[0].influence_score > 0.0


def test_enrich_speakers_skips_speakers_without_linkedin_url() -> None:
    speaker = SpeakerSchema(name="Anonymous", linkedin_url="")
    enriched = enrich_speakers([speaker], api_key="fake")
    assert enriched[0].influence_score == 0.0


def test_enrich_speakers_continues_on_api_error(sample_speaker: SpeakerSchema) -> None:
    with patch("backend.tools.linkedin_tool.requests.get") as mock_get:
        mock_get.return_value = _make_response(500, {"error": "Server error"})
        enriched = enrich_speakers([sample_speaker], api_key="fake")

    # Original speaker is returned unchanged on error
    assert enriched[0].name == sample_speaker.name
    assert enriched[0].influence_score == 0.0
