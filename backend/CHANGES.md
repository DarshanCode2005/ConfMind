# Changes in backend/

## 2026-04-16

### `config.py` — Anthropic-first LLM configuration
- Added `ANTHROPIC_MODEL` (default: `claude-3-haiku-20240307`) — primary LLM model slug.
- Added `ANTHROPIC_MAX_TOKENS` (default: `4096`) — token budget for Claude; does NOT apply free-tier cap.
- Added `MAX_TOKENS_FALLBACK` (default: `1100`) — token cap applied **only** to non-Anthropic fallback models (OpenRouter, OpenAI, Gemini) to stay within free-tier limits.
- Added `MAX_TOKENS` as a legacy alias pointing to `MAX_TOKENS_FALLBACK` (backward compatibility).
- Added `MAX_AGENTS` (default: `7`) — hard ceiling on concurrent agent spawns enforced at graph-build time.

### `orchestrator.py` — Agent spawn cap guard
- Imported `MAX_AGENTS` from `backend.config`.
- Added `MAX_AGENTS` guard inside `_build_graph()`: if more than `MAX_AGENTS` agents are successfully imported, excess ones are demoted to passthrough stubs and a `warnings.warn()` is emitted.
- Changed `_build_graph()` docstring to document the cap behaviour.

### `main.py` — Startup key validation
- Updated `lifespan()` to warn on missing `ANTHROPIC_API_KEY` (primary LLM) first.
- Secondary warning for missing `OPENAI_API_KEY` only if Anthropic key IS present (scraper_tool still needs it).
- Updated module docstring to reflect Anthropic as the primary LLM.
