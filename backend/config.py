"""
config.py - Centralised LLM + runtime configuration for all ConfMind agents.

Every agent reads from this module instead of duplicating magic constants.

Environment variables (all optional - sensible defaults are provided):
    ANTHROPIC_API_KEY       Primary LLM provider key (Claude).
    ANTHROPIC_MODEL         Claude model slug (default: claude-3-haiku-20240307).
    ANTHROPIC_MAX_TOKENS    Max output tokens when Claude is primary (default: 4096).

    OPENROUTER_API_KEY      Fallback LLM provider key.
    PRIMARY_MODEL           OpenRouter primary model slug.
    SECONDARY_MODEL         OpenRouter secondary model slug.

    OLLAMA_MODEL            Local Ollama model name.
    OLLAMA_NUM_CTX          Ollama context window size.

    MAX_TOKENS_FALLBACK     Token cap applied ONLY to non-Anthropic (fallback) models.
                            Set to 1100 to stay within free-tier limits.

    AGENT_TEMPERATURE       Default LLM sampling temperature (default: 0.3).
    AGENT_MAX_RETRIES       LangChain retry count before fallback triggers (default: 1).
    MAX_AGENTS              Maximum number of concurrent agent spawns (default: 7).

Usage:
    from backend.config import ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS, MAX_AGENTS
"""

from __future__ import annotations

import os

# ── Anthropic (Primary LLM) ───────────────────────────────────────────────────
# Claude Haiku is fast, cheap, and generous on context.
# max_tokens is a REQUIRED param for Anthropic API - do not remove it.
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_MAX_TOKENS: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096"))

# ── Fallback token cap (free-tier guard) ──────────────────────────────────────
# Applied ONLY to non-Anthropic models (OpenRouter free tier, OpenAI free tier).
# Free-tier OpenRouter caps output at ~1100 tokens per request.
# This does NOT apply to Claude (which uses ANTHROPIC_MAX_TOKENS above).
MAX_TOKENS_FALLBACK: int = int(os.getenv("MAX_TOKENS_FALLBACK", "1100"))

# Legacy alias - kept for any code that still imports MAX_TOKENS directly.
# Points to the fallback cap so existing fallback models are not broken.
MAX_TOKENS: int = MAX_TOKENS_FALLBACK

# ── Default reasoning parameters ─────────────────────────────────────────────
TEMPERATURE: float = float(os.getenv("AGENT_TEMPERATURE", "0.3"))
MAX_RETRIES: int = int(os.getenv("AGENT_MAX_RETRIES", "1"))

# ── OpenRouter model selection ────────────────────────────────────────────────
PRIMARY_MODEL: str = os.getenv("PRIMARY_MODEL", "google/gemma-2-27b-it")
SECONDARY_MODEL: str = os.getenv("SECONDARY_MODEL", "google/gemma-2-9b-it")

# ── Local Ollama ──────────────────────────────────────────────────────────────
LOCAL_MODEL: str = os.getenv("OLLAMA_MODEL", "confmind-planner")
OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "32768"))

# ── API Endpoints ─────────────────────────────────────────────────────────────
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

# ── Agent Spawn Cap ───────────────────────────────────────────────────────────
# Hard ceiling on the number of concurrent agents the orchestrator may spawn.
# Keep at 7 to avoid exhausting API rate limits and memory simultaneously.
MAX_AGENTS: int = int(os.getenv("MAX_AGENTS", "7"))
