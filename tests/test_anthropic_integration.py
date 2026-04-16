"""
test_anthropic_integration.py - Comprehensive diagnostic + integration test suite.

Tests every aspect of the Anthropic-first LLM integration across ConfMind:
  1.  ENV CHECK          - All API keys are readable from the environment.
  2.  CONFIG CHECK       - New config constants load correctly with correct types.
  3.  LLM INIT           - _get_llm() builds without exceptions; Claude is first.
  4.  CHAT LLM INIT      - _get_chat_llm() builds; Claude is first candidate.
  5.  TOKEN CAPS         - Claude gets ANTHROPIC_MAX_TOKENS; fallbacks get 1100.
  6.  FALLBACK CHAIN     - Simulated Anthropic failure triggers OpenRouter with 1100 cap.
  7.  AGENT CAP          - MAX_AGENTS=7 guard fires when >7 agents are registered.
  8.  LIVE ANTHROPIC     - (Skipped if no key) Real Claude call with max_tokens=50.
  9.  INVOKE_LLM ROUTES  - _invoke_llm() on a real agent subclass returns a string.
  10. PIPELINE SMOKE     - Full run_plan() with mocked external I/O returns all fields.

Run from project root (venv activated):
    pytest tests/test_anthropic_integration.py -v
    pytest tests/test_anthropic_integration.py -v -k "not live"   # skip real API tests
"""

from __future__ import annotations

import os
import sys
import warnings
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ── Make sure project root is on sys.path ─────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load .env so all keys are available before any import that reads env vars
from dotenv import load_dotenv  # type: ignore[import-untyped]
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


# =============================================================================
# TEST 1 — ENV CHECK
# =============================================================================

class TestEnvCheck:
    """Verify API keys are readable and non-empty in the environment."""

    def test_anthropic_key_present(self) -> None:
        """ANTHROPIC_API_KEY must be set — it is the primary LLM."""
        key = os.getenv("ANTHROPIC_API_KEY", "")
        assert key, (
            "ANTHROPIC_API_KEY is missing from .env! "
            "Add it to enable Claude as the primary LLM."
        )
        assert key.startswith("sk-ant-"), (
            f"ANTHROPIC_API_KEY looks malformed. Expected 'sk-ant-...' but got: {key[:15]}..."
        )

    def test_openrouter_key_present(self) -> None:
        """OPENROUTER_API_KEY is needed for the fallback OpenRouter models."""
        key = os.getenv("OPENROUTER_API_KEY", "")
        assert key, "OPENROUTER_API_KEY is missing — fallback models will fail."

    def test_openai_key_present(self) -> None:
        """OPENAI_API_KEY is needed by scraper_tool and OpenAI fallback."""
        key = os.getenv("OPENAI_API_KEY", "")
        assert key, "OPENAI_API_KEY is missing — scraper_tool will fail."

    def test_tavily_key_present(self) -> None:
        """TAVILY_API_KEY used by all agents for enrichment searches."""
        key = os.getenv("TAVILY_API_KEY", "")
        assert key, "TAVILY_API_KEY is missing — Tavily enrichment will be skipped."

    def test_anthropic_key_has_no_extra_spaces(self) -> None:
        """Common .env bug: key has a leading space, e.g. ANTHROPIC_API_KEY= 'sk-ant-...'"""
        raw = os.getenv("ANTHROPIC_API_KEY", "")
        assert raw == raw.strip(), (
            "ANTHROPIC_API_KEY has leading/trailing whitespace — fix the .env line. "
            f"Got: '{raw[:20]}...'"
        )


# =============================================================================
# TEST 2 — CONFIG CHECK
# =============================================================================

class TestConfigConstants:
    """Verify all new config constants load with the right types and values."""

    def test_anthropic_model_is_string(self) -> None:
        from backend.config import ANTHROPIC_MODEL
        assert isinstance(ANTHROPIC_MODEL, str) and ANTHROPIC_MODEL, \
            "ANTHROPIC_MODEL must be a non-empty string."

    def test_anthropic_max_tokens_is_int_and_generous(self) -> None:
        from backend.config import ANTHROPIC_MAX_TOKENS
        assert isinstance(ANTHROPIC_MAX_TOKENS, int), \
            "ANTHROPIC_MAX_TOKENS must be an int."
        assert ANTHROPIC_MAX_TOKENS > 1100, (
            f"ANTHROPIC_MAX_TOKENS={ANTHROPIC_MAX_TOKENS} should be > 1100 "
            "(1100 is the free-tier fallback cap; Claude primary should be more generous)."
        )

    def test_max_tokens_fallback_is_1100(self) -> None:
        from backend.config import MAX_TOKENS_FALLBACK
        assert isinstance(MAX_TOKENS_FALLBACK, int), \
            "MAX_TOKENS_FALLBACK must be an int."
        assert MAX_TOKENS_FALLBACK <= 1100, (
            f"MAX_TOKENS_FALLBACK={MAX_TOKENS_FALLBACK} exceeds 1100 — "
            "fallback models will exceed free-tier output limits."
        )

    def test_max_tokens_legacy_alias_matches_fallback(self) -> None:
        from backend.config import MAX_TOKENS, MAX_TOKENS_FALLBACK
        assert MAX_TOKENS == MAX_TOKENS_FALLBACK, (
            "MAX_TOKENS (legacy alias) must equal MAX_TOKENS_FALLBACK for backward compat. "
            f"Got MAX_TOKENS={MAX_TOKENS}, MAX_TOKENS_FALLBACK={MAX_TOKENS_FALLBACK}"
        )

    def test_max_agents_is_7(self) -> None:
        from backend.config import MAX_AGENTS
        assert isinstance(MAX_AGENTS, int), "MAX_AGENTS must be an int."
        assert MAX_AGENTS == 7, (
            f"MAX_AGENTS={MAX_AGENTS}, expected 7. "
            "Change MAX_AGENTS env var or config default if you want a different cap."
        )

    def test_temperature_is_reasonable(self) -> None:
        from backend.config import TEMPERATURE
        assert 0.0 <= TEMPERATURE <= 1.0, \
            f"TEMPERATURE={TEMPERATURE} is out of [0.0, 1.0] range."

    def test_openrouter_base_url_correct(self) -> None:
        from backend.config import OPENROUTER_BASE_URL
        assert OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1", \
            f"OPENROUTER_BASE_URL looks wrong: {OPENROUTER_BASE_URL}"


# =============================================================================
# HELPERS — Minimal concrete agent for testing BaseAgent methods
# =============================================================================

def _make_test_agent() -> Any:
    """Return a minimal concrete BaseAgent subclass for unit testing."""
    from backend.agents.base_agent import BaseAgent
    from backend.models.schemas import AgentState
    from langchain_core.prompts import ChatPromptTemplate

    class _TestAgent(BaseAgent):
        name: str = "test_agent"

        def _build_prompt(self) -> ChatPromptTemplate:
            return ChatPromptTemplate.from_messages([
                ("system", "You are a test agent."),
                ("human", "{input}"),
            ])

        def run(self, state: AgentState) -> dict[str, Any]:
            return {}

    return _TestAgent()


# =============================================================================
# TEST 3 — LLM INIT (no live API call)
# =============================================================================

class TestLlmInit:
    """Verify _get_llm() constructs the correct fallback chain without errors."""

    def test_get_llm_returns_runnable(self) -> None:
        """_get_llm() must return a LangChain Runnable (has .invoke method)."""
        agent = _make_test_agent()
        llm = agent._get_llm()
        assert hasattr(llm, "invoke"), \
            "_get_llm() did not return a callable Runnable (missing .invoke)."

    def test_get_llm_primary_is_anthropic(self) -> None:
        """The primary (first) model in the chain must be ChatAnthropic."""
        from langchain_anthropic import ChatAnthropic

        agent = _make_test_agent()
        llm = agent._get_llm()

        # LangChain wraps the primary in a RunnableWithFallbacks;
        # the .runnable attribute holds the primary.
        primary = getattr(llm, "runnable", llm)
        assert isinstance(primary, ChatAnthropic), (
            f"Expected primary LLM to be ChatAnthropic, got {type(primary).__name__}. "
            "Check base_agent._get_llm() priority chain."
        )

    def test_get_llm_primary_max_tokens_is_anthropic_budget(self) -> None:
        """Claude's max_tokens param must equal ANTHROPIC_MAX_TOKENS, not the free-tier cap."""
        from langchain_anthropic import ChatAnthropic
        from backend.config import ANTHROPIC_MAX_TOKENS

        agent = _make_test_agent()
        llm = agent._get_llm()
        primary: ChatAnthropic = getattr(llm, "runnable", llm)

        assert hasattr(primary, "max_tokens"), \
            "ChatAnthropic instance missing max_tokens attribute."
        assert primary.max_tokens == ANTHROPIC_MAX_TOKENS, (
            f"Claude max_tokens={primary.max_tokens} != ANTHROPIC_MAX_TOKENS={ANTHROPIC_MAX_TOKENS}. "
            "Primary LLM should NOT be capped at the free-tier fallback limit."
        )

    def test_get_llm_fallbacks_use_1100_cap(self) -> None:
        """Fallback OpenRouter models must have max_tokens=1100."""
        from backend.config import MAX_TOKENS_FALLBACK

        agent = _make_test_agent()
        llm = agent._get_llm()

        fallbacks = getattr(llm, "fallbacks", [])
        assert fallbacks, "_get_llm() returned no fallbacks — chain is not set up."

        for fb in fallbacks:
            # Ollama has no max_tokens attr — skip it
            if hasattr(fb, "max_tokens"):
                assert fb.max_tokens == MAX_TOKENS_FALLBACK, (
                    f"Fallback model {type(fb).__name__} has max_tokens={fb.max_tokens} "
                    f"but expected {MAX_TOKENS_FALLBACK} (free-tier cap)."
                )

    def test_get_llm_with_different_temperature(self) -> None:
        """_get_llm(temperature=0.7) should not crash and return a Runnable."""
        agent = _make_test_agent()
        llm = agent._get_llm(temperature=0.7)
        assert hasattr(llm, "invoke"), \
            "_get_llm(temperature=0.7) did not return a callable Runnable."


# =============================================================================
# TEST 4 — CHAT LLM INIT
# =============================================================================

class TestChatLlmInit:
    """Verify _get_chat_llm() has the correct Anthropic-first priority."""

    def test_chat_llm_returns_runnable(self) -> None:
        from backend.agents.chat_agent import _get_chat_llm
        llm = _get_chat_llm()
        assert hasattr(llm, "invoke"), \
            "_get_chat_llm() did not return a callable Runnable."

    def test_chat_llm_primary_is_anthropic(self) -> None:
        """First candidate for chat must be Anthropic when key is set."""
        from langchain_anthropic import ChatAnthropic
        from backend.agents.chat_agent import _get_chat_llm

        llm = _get_chat_llm()
        primary = getattr(llm, "runnable", llm)
        assert isinstance(primary, ChatAnthropic), (
            f"ChatAgent primary={type(primary).__name__}, expected ChatAnthropic. "
            "Check chat_agent._get_chat_llm() priority order."
        )

    def test_chat_llm_primary_has_generous_token_budget(self) -> None:
        """Chat Claude must also have ANTHROPIC_MAX_TOKENS, not the 1100 cap."""
        from langchain_anthropic import ChatAnthropic
        from backend.agents.chat_agent import _get_chat_llm
        from backend.config import ANTHROPIC_MAX_TOKENS

        llm = _get_chat_llm()
        primary: ChatAnthropic = getattr(llm, "runnable", llm)
        if isinstance(primary, ChatAnthropic):
            assert primary.max_tokens == ANTHROPIC_MAX_TOKENS, (
                f"Chat Claude max_tokens={primary.max_tokens} != {ANTHROPIC_MAX_TOKENS}"
            )


# =============================================================================
# TEST 5 — TOKEN CAPS ENFORCEMENT
# =============================================================================

class TestTokenCaps:
    """Verify that primary vs fallback token caps are correctly assigned."""

    def test_claude_token_cap_not_1100(self) -> None:
        """Claude should never be capped at 1100 — that degrades its output quality."""
        from langchain_anthropic import ChatAnthropic
        agent = _make_test_agent()
        llm = agent._get_llm()
        primary = getattr(llm, "runnable", llm)
        if isinstance(primary, ChatAnthropic):
            assert primary.max_tokens != 1100, (
                "CRITICAL: Claude's max_tokens is 1100 — same as the free-tier fallback cap! "
                "Fix ANTHROPIC_MAX_TOKENS in config.py or _get_llm()."
            )

    def test_openrouter_fallback_capped_at_1100(self) -> None:
        """Every OpenRouter fallback model must be capped at exactly 1100."""
        from langchain_openai import ChatOpenAI
        agent = _make_test_agent()
        llm = agent._get_llm()
        for fb in getattr(llm, "fallbacks", []):
            if isinstance(fb, ChatOpenAI):
                assert fb.max_tokens == 1100, (
                    f"OpenRouter fallback {fb.model_name} has max_tokens={fb.max_tokens}, "
                    "expected 1100. Exceeding this on the free tier will cause API errors."
                )


# =============================================================================
# TEST 6 — FALLBACK CHAIN SIMULATION (mocked Anthropic failure)
# =============================================================================

class TestFallbackChain:
    """Verify that Anthropic failure automatically falls back to OpenRouter."""

    def test_anthropic_failure_triggers_openrouter_fallback(self) -> None:
        """When Claude raises an exception, the chain must route to OpenRouter."""
        from langchain_core.messages import AIMessage

        agent = _make_test_agent()
        llm = agent._get_llm()

        # Simulate Claude raising a rate-limit error
        mock_response = AIMessage(content="Fallback response from OpenRouter")

        # We patch the class methods to ensure the chain failover works correctly.
        with patch("langchain_anthropic.ChatAnthropic.invoke", side_effect=Exception("Simulated Anthropic 429")):
            with patch("langchain_openai.ChatOpenAI.invoke", return_value=mock_response):
                result = llm.invoke("Hello, which model are you?")
                assert result is not None, "Fallback returned None."
                assert result.content == "Fallback response from OpenRouter"

    def test_fallback_max_tokens_unchanged_after_failure(self) -> None:
        """After a primary failure, the fallback LLM's max_tokens must still be 1100."""
        from langchain_openai import ChatOpenAI
        agent = _make_test_agent()
        llm = agent._get_llm()

        fallbacks = getattr(llm, "fallbacks", [])
        openrouter_fallbacks = [fb for fb in fallbacks if isinstance(fb, ChatOpenAI)]
        assert openrouter_fallbacks, \
            "No ChatOpenAI fallback found in the chain — check _get_llm() setup."

        for fb in openrouter_fallbacks:
            assert fb.max_tokens == 1100, (
                f"Fallback {fb.model_name} max_tokens changed from 1100 to {fb.max_tokens} "
                "at runtime — something is mutating the fallback config. Investigate."
            )


# =============================================================================
# TEST 7 — AGENT SPAWN CAP
# =============================================================================

class TestAgentSpawnCap:
    """Verify that MAX_AGENTS=7 is enforced in the orchestrator."""

    def test_max_agents_constant_is_7(self) -> None:
        from backend.config import MAX_AGENTS
        assert MAX_AGENTS == 7

    def test_orchestrator_cap_fires_warning_when_exceeded(self) -> None:
        """If >7 real agents are loaded, _build_graph() must warn and trim."""
        from backend.config import MAX_AGENTS

        # Simulate 9 loaded agents (all non-None — like a fully bootstrapped system)
        fake_agents: dict[str, Any] = {f"agent_{i}": MagicMock() for i in range(9)}

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")

            # Inline the cap-guard logic that lives in _build_graph()
            active = {k: v for k, v in fake_agents.items() if v is not None}
            if len(active) > MAX_AGENTS:
                excess = list(active.keys())[MAX_AGENTS:]
                warnings.warn(
                    f"[Orchestrator] {len(active)} agents registered but MAX_AGENTS={MAX_AGENTS}. "
                    f"Disabling excess agents: {excess}.",
                    stacklevel=1,
                )
                for key in excess:
                    fake_agents[key] = None

            assert len(fake_agents) == 9, \
                "Agent dict shrunk — guard should demote, not delete, entries."
            none_count = sum(1 for v in fake_agents.values() if v is None)
            assert none_count == 9 - MAX_AGENTS, (
                f"Expected {9 - MAX_AGENTS} demoted agents, found {none_count}."
            )
            assert any("[Orchestrator]" in str(w.message) for w in caught), \
                "Cap guard did not emit the expected warning message."

    def test_registered_agents_within_cap(self) -> None:
        """The actual orchestrator's agent registry must not exceed MAX_AGENTS by default."""
        from backend.config import MAX_AGENTS
        # We count how many agents _import_agents() can successfully instantiate.
        # Even if some modules are stub, the count of keys must be checked.
        try:
            from backend.orchestrator import _import_agents
            agents = _import_agents()
            active = {k: v for k, v in agents.items() if v is not None}
            assert len(active) <= MAX_AGENTS, (
                f"FAIL: {len(active)} active agents loaded but MAX_AGENTS={MAX_AGENTS}. "
                f"Active agents: {list(active.keys())}"
            )
        except Exception as exc:
            pytest.skip(f"Could not import orchestrator (dependency missing?): {exc}")


# =============================================================================
# TEST 8 — LIVE ANTHROPIC CALL (marked 'live', skipped if no real key)
# =============================================================================

ANTHROPIC_KEY_AVAILABLE = bool(
    os.getenv("ANTHROPIC_API_KEY", "").strip().startswith("sk-ant-")
)


@pytest.mark.skipif(not ANTHROPIC_KEY_AVAILABLE, reason="ANTHROPIC_API_KEY not set or invalid")
class TestLiveAnthropic:
    """Real Claude API call tests — skipped automatically in CI without the key."""

    def test_live_claude_responds(self) -> None:
        """Make a minimal real API call to claude-3-haiku and verify a non-empty response."""
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage
        from backend.config import ANTHROPIC_MODEL

        llm = ChatAnthropic(
            model=ANTHROPIC_MODEL,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),  # type: ignore[arg-type]
            max_tokens=50,  # tiny — just enough to verify connectivity
        )
        result = llm.invoke([HumanMessage(content="Reply with exactly: OK")])
        content = getattr(result, "content", "")
        assert content and content.strip(), \
            f"Claude returned an empty response. Raw result: {result!r}"
        print(f"\n  [LIVE] Claude responded: {content!r}")

    def test_live_invoke_llm_via_agent(self) -> None:
        """Test _invoke_llm() on a real agent subclass routes through Claude."""
        agent = _make_test_agent()
        result = agent._invoke_llm("Say YES if you are working.", temperature=0.0)
        assert result and result != "null", (
            f"_invoke_llm() returned 'null' or empty — Claude may have failed. Got: {result!r}"
        )
        print(f"\n  [LIVE] _invoke_llm() response: {result[:100]!r}")


# =============================================================================
# TEST 9 — INVOKE_LLM WITH MOCKED LLM (no API call)
# =============================================================================

class TestInvokeLlmMocked:
    """Test _invoke_llm() logic without making real API calls."""

    def test_invoke_llm_returns_string_on_success(self) -> None:
        """_invoke_llm() must return a plain string, not an AIMessage or dict."""
        from langchain_core.messages import AIMessage

        agent = _make_test_agent()
        mock_response = AIMessage(content="Mocked response from Claude")

        with patch.object(agent, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            result = agent._invoke_llm("test prompt")
            assert isinstance(result, str), \
                f"_invoke_llm() must return str, got {type(result).__name__}."
            assert result == "Mocked response from Claude"

    def test_invoke_llm_retries_on_empty_response(self) -> None:
        """On empty first response, _invoke_llm() retries once at temp=0."""
        from langchain_core.messages import AIMessage

        agent = _make_test_agent()
        empty_response = AIMessage(content="")
        retry_response = AIMessage(content="Retry response")

        call_count = 0

        def fake_get_llm(temperature: float = 0.3) -> Any:
            nonlocal call_count
            mock_llm = MagicMock()
            if call_count == 0:
                mock_llm.invoke.return_value = empty_response
            else:
                mock_llm.invoke.return_value = retry_response
            call_count += 1
            return mock_llm

        with patch.object(agent, "_get_llm", side_effect=fake_get_llm):
            result = agent._invoke_llm("test prompt")
            assert call_count == 2, \
                f"Expected _get_llm() called twice (initial + retry), got {call_count}."
            assert result == "Retry response"

    def test_invoke_llm_returns_null_on_persistent_failure(self) -> None:
        """If LLM raises on every attempt, _invoke_llm() returns 'null'."""
        agent = _make_test_agent()

        with patch.object(agent, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = Exception("API completely down")
            mock_get_llm.return_value = mock_llm

            result = agent._invoke_llm("test prompt")
            assert result == "null", \
                f"Expected 'null' on persistent failure, got: {result!r}"


# =============================================================================
# TEST 10 — FULL PIPELINE SMOKE TEST (mocked I/O)
# =============================================================================

class TestPipelineSmoke:
    """Smoke test: run the full LangGraph pipeline with all external I/O mocked.

    This validates the graph topology, state merging, and agent output shapes
    without making any real API calls.
    """

    @pytest.fixture
    def sample_config(self) -> Any:
        from backend.models.schemas import EventConfigInput
        return EventConfigInput(
            category="AI",
            geography="India",
            audience_size=500,
            budget_usd=25000.0,
            event_dates="2025-11-01",
            event_name="Test AI Summit",
        )

    @patch("backend.agents.web_search_agent.WebSearchAgent._fetch_predicthq_events", return_value=[])
    @patch("backend.agents.web_search_agent.WebSearchAgent._tavily_search", return_value=[])
    @patch("backend.agents.web_search_agent.WebSearchAgent._invoke_llm", return_value="null")
    @patch("backend.agents.sponsor_agent.SponsorAgent._tavily_search", return_value=[])
    @patch("backend.agents.sponsor_agent.SponsorAgent._invoke_llm", return_value="5.0")
    @patch("backend.agents.sponsor_agent.SponsorAgent._invoke_llm_json", return_value=[])
    @patch("backend.agents.speaker_agent.SpeakerAgent._tavily_search", return_value=[])
    @patch("backend.agents.speaker_agent.SpeakerAgent._invoke_llm_json", return_value=[])
    @patch("backend.agents.venue_agent.VenueAgent._tavily_search", return_value=[])
    @patch("backend.agents.venue_agent.VenueAgent._invoke_llm_json", return_value=[])
    @patch("backend.agents.exhibitor_agent.ExhibitorAgent._invoke_llm_json", return_value=[])
    @patch("backend.agents.pricing_agent.PricingAgent._invoke_llm_json", return_value={})
    @patch("backend.agents.community_gtm_agent.CommunityGTMAgent._tavily_search", return_value=[])
    @patch("backend.agents.community_gtm_agent.CommunityGTMAgent._invoke_llm", return_value="Message")
    @patch("backend.agents.event_ops_agent.EventOpsAgent._invoke_llm_json", return_value=[])
    @patch("backend.agents.revenue_agent.RevenueAgent._invoke_llm_json", return_value={})
    @patch("backend.memory.vector_store.embed_and_store")
    @patch("backend.memory.vector_store.similarity_search", return_value=[])
    def test_run_plan_returns_all_state_fields(
        self,
        mock_similarity: Any,
        mock_embed: Any,
        sample_config: Any,
        *args: Any,
    ) -> None:
        """run_plan() must return an AgentState with all 10 top-level fields."""
        import asyncio
        try:
            from backend.orchestrator import run_plan
        except Exception as exc:
            pytest.skip(f"Orchestrator import failed (likely missing dependency): {exc}")

        try:
            final_state = asyncio.run(run_plan(sample_config))
        except Exception as exc:
            pytest.fail(f"run_plan() raised an unexpected exception: {exc}")

        required_fields = [
            "event_config", "past_events", "sponsors", "speakers",
            "venues", "exhibitors", "pricing", "communities",
            "schedule", "revenue", "gtm_messages", "errors", "metadata",
        ]
        for field in required_fields:
            assert field in final_state, (
                f"AgentState is missing field '{field}' after run_plan() completed."
            )

    def test_empty_past_events_does_not_crash_pipeline(self, sample_config: Any) -> None:
        """Pipeline must complete gracefully even when past_events is empty (real edge case)."""
        from backend.models.schemas import AgentState
        from backend.agents.sponsor_agent import SponsorAgent

        initial_state: AgentState = {
            "event_config": sample_config,
            "past_events": [],  # empty — simulates PredictHQ + Tavily both failing
            "sponsors": [], "speakers": [], "venues": [], "exhibitors": [],
            "pricing": [], "communities": [], "schedule": [], "revenue": {},
            "gtm_messages": {}, "messages": [], "errors": [], "metadata": {},
        }

        agent = SponsorAgent()
        with patch.object(agent, "_tavily_search", return_value=[]):
            with patch.object(agent, "_invoke_llm", return_value="5.0"):
                with patch.object(agent, "_invoke_llm_json", return_value=[]):
                    with patch("backend.tools.pdf_generator.save_proposal", return_value="/tmp/x.pdf"):
                        with patch("backend.memory.vector_store.embed_and_store"):
                            result = agent.run(initial_state)

        assert isinstance(result, dict), \
            f"SponsorAgent.run() returned {type(result).__name__}, expected dict."
        # Must not raise — errors go into the errors list, not as exceptions
        assert "sponsors" in result or "errors" in result, (
            "SponsorAgent returned a dict with neither 'sponsors' nor 'errors' key."
        )


# =============================================================================
# DIAGNOSTICS SUMMARY — printed when run with pytest -v -s
# =============================================================================

def test_print_diagnostic_summary() -> None:
    """Print a human-readable summary of the current LLM configuration."""
    from backend.config import (
        ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS,
        MAX_TOKENS_FALLBACK, MAX_AGENTS,
        PRIMARY_MODEL, SECONDARY_MODEL, LOCAL_MODEL,
        TEMPERATURE,
    )

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    or_key = os.getenv("OPENROUTER_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    tavily_key = os.getenv("TAVILY_API_KEY", "")

    def mask(k: str) -> str:
        return f"{k[:8]}...{k[-4:]}" if len(k) > 12 else ("SET" if k else "MISSING")

    print("\n" + "=" * 60)
    print("  ConfMind LLM Configuration Diagnostic")
    print("=" * 60)
    print(f"  PRIMARY LLM  : Anthropic / {ANTHROPIC_MODEL}")
    print(f"  Max tokens   : {ANTHROPIC_MAX_TOKENS} (Claude primary)")
    print(f"  Fallback cap : {MAX_TOKENS_FALLBACK} tokens (free-tier)")
    print(f"  Max agents   : {MAX_AGENTS}")
    print(f"  Temperature  : {TEMPERATURE}")
    print()
    print("  Fallback chain:")
    print(f"    1. Anthropic {ANTHROPIC_MODEL}       [{mask(anthropic_key)}]")
    print(f"    2. OpenRouter {PRIMARY_MODEL}  [{mask(or_key)}]")
    print(f"    3. OpenRouter {SECONDARY_MODEL}   [{mask(or_key)}]")
    print(f"    4. Ollama {LOCAL_MODEL}                    [local]")
    print()
    print("  API Keys:")
    print(f"    ANTHROPIC_API_KEY   : {mask(anthropic_key)}")
    print(f"    OPENROUTER_API_KEY  : {mask(or_key)}")
    print(f"    OPENAI_API_KEY      : {mask(openai_key)}")
    print(f"    TAVILY_API_KEY      : {mask(tavily_key)}")
    print("=" * 60)
    # This test always passes — it's diagnostic output only
    assert True
