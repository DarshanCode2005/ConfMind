"""
linkedin_tool.py — LinkedIn profile enrichment via RapidAPI.

Fetches public LinkedIn profile data (followers, headline, connection count,
recent post count) and derives an influence_score used by the Speaker Agent
when ranking speakers.

Environment variables
─────────────────────
RAPIDAPI_KEY   Required.  Sign up at https://rapidapi.com and subscribe to
               a LinkedIn People Search API (e.g. "Fresh LinkedIn Profile Data").

Public interface
────────────────
get_profile(linkedin_url)                -> LinkedInProfile
calculate_influence_score(profile)       -> float   (0.0 - 10.0)
enrich_speakers(speakers)               -> list[SpeakerSchema]

Errors
──────
LinkedInAPIError     Raised for HTTP errors.
LinkedInRateLimitError   Raised specifically on 429 (rate-limited).

Retry strategy
──────────────
`get_profile` retries up to MAX_RETRIES times with exponential back-off on 429.

Usage example
─────────────
    from backend.tools.linkedin_tool import enrich_speakers
    from backend.models.schemas import SpeakerSchema

    speakers = [SpeakerSchema(name="Jane Doe", linkedin_url="https://linkedin.com/in/janedoe")]
    enriched = enrich_speakers(speakers)
    print(enriched[0].influence_score)
"""

from __future__ import annotations

import os
import time

import requests
from dotenv import load_dotenv

from backend.models.schemas import LinkedInProfile, SpeakerSchema

load_dotenv()

_RAPIDAPI_HOST = "fresh-linkedin-profile-data.p.rapidapi.com"
_PROFILE_URL = f"https://{_RAPIDAPI_HOST}/get-linkedin-profile"
MAX_RETRIES = 3
_BASE_BACKOFF_S = 1.0  # seconds; doubles each retry


# ─────────────────────────────────────────────
# Custom exceptions
# ─────────────────────────────────────────────


class LinkedInAPIError(Exception):
    """Raised on any non-successful HTTP response from the LinkedIn RapidAPI."""

    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"LinkedIn API error {status_code}: {body}")
        self.status_code = status_code


class LinkedInRateLimitError(LinkedInAPIError):
    """Raised specifically on HTTP 429 (Too Many Requests)."""


# ─────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────


def _get_api_key() -> str:
    key = os.getenv("RAPIDAPI_KEY", "")
    if not key:
        raise OSError("RAPIDAPI_KEY is not set. Add it to your .env file or export it.")
    return key


def _build_headers(api_key: str) -> dict[str, str]:
    return {
        "x-rapidapi-host": _RAPIDAPI_HOST,
        "x-rapidapi-key": api_key,
    }


def _parse_profile(data: dict, linkedin_url: str) -> LinkedInProfile:
    """Map raw RapidAPI JSON payload to a LinkedInProfile model."""
    return LinkedInProfile(
        name=data.get("full_name", ""),
        headline=data.get("headline", ""),
        followers=int(data.get("follower_count", 0) or 0),
        connections=int(data.get("connection_count", 0) or 0),
        recent_posts_count=int(data.get("posts_count", 0) or 0),
        linkedin_url=linkedin_url,
    )


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────


def get_profile(
    linkedin_url: str,
    *,
    api_key: str | None = None,
) -> LinkedInProfile:
    """Fetch a LinkedIn profile, retrying on rate-limit (429).

    Args:
        linkedin_url: Full LinkedIn profile URL, e.g.
                      "https://www.linkedin.com/in/username"
        api_key:      Override RAPIDAPI_KEY env var (useful in tests).

    Returns:
        A LinkedInProfile with follower count, headline, etc.

    Raises:
        LinkedInRateLimitError: If still rate-limited after MAX_RETRIES.
        LinkedInAPIError:       For other HTTP errors.
    """
    key = api_key or _get_api_key()
    headers = _build_headers(key)
    params = {"linkedin_url": linkedin_url}

    last_error: LinkedInAPIError | None = None
    for attempt in range(MAX_RETRIES):
        response = requests.get(_PROFILE_URL, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return _parse_profile(response.json(), linkedin_url)
        if response.status_code == 429:
            wait = _BASE_BACKOFF_S * (2**attempt)
            time.sleep(wait)
            last_error = LinkedInRateLimitError(response.status_code, response.text)
        else:
            raise LinkedInAPIError(response.status_code, response.text)

    # Exhausted retries
    raise last_error or LinkedInRateLimitError(429, "Rate limit exceeded")


def calculate_influence_score(profile: LinkedInProfile) -> float:
    """Compute a normalised influence score in [0.0, 10.0].

    Formula (deterministic, no LLM):
      - Follower contribution:  log10(followers + 1) / log10(100_001) * 6.0  (max 6 pts)
      - Posts contribution:     min(recent_posts_count, 10) / 10 * 2.0       (max 2 pts)
      - Connections bonus:      min(connections, 500) / 500 * 2.0             (max 2 pts)

    The thresholds are calibrated so a speaker with 100k followers, active
    posting history and 500 connections scores close to 10.0.
    """
    import math

    follower_pts = (math.log10(profile.followers + 1) / math.log10(100_001)) * 6.0
    posts_pts = (min(profile.recent_posts_count, 10) / 10) * 2.0
    conn_pts = (min(profile.connections, 500) / 500) * 2.0
    score = follower_pts + posts_pts + conn_pts
    return round(min(score, 10.0), 2)


def enrich_speakers(
    speakers: list[SpeakerSchema],
    *,
    api_key: str | None = None,
) -> list[SpeakerSchema]:
    """Bulk-enrich a list of SpeakerSchema objects with LinkedIn influence scores.

    Profiles without a linkedin_url are skipped gracefully (score stays 0.0).
    API errors per speaker are caught and logged; enrichment continues for the rest.

    Args:
        speakers: SpeakerSchema objects (may have empty linkedin_url).
        api_key:  Override RAPIDAPI_KEY env var.

    Returns:
        The same list with influence_score populated for speakers whose
        linkedin_url was accessible.
    """
    enriched: list[SpeakerSchema] = []
    for speaker in speakers:
        if not speaker.linkedin_url:
            enriched.append(speaker)
            continue
        try:
            profile = get_profile(speaker.linkedin_url, api_key=api_key)
            score = calculate_influence_score(profile)
            # Pydantic v2: model_copy(update=…) produces a new immutable instance
            enriched.append(speaker.model_copy(update={"influence_score": score}))
        except (OSError, LinkedInAPIError) as exc:
            # Non-fatal: keep original speaker, log for debugging
            print(f"[linkedin_tool] Could not enrich {speaker.name}: {exc}")
            enriched.append(speaker)
    return enriched
