# Changes in backend/agents/

## 2026-04-16

### `base_agent.py` — Anthropic-first LLM fallback chain
- **Rewrote `_get_llm()`** to place `ChatAnthropic` (Claude 3 Haiku) as the first-priority model.
- New priority chain: **Claude → OpenRouter 27B → OpenRouter 9B → Ollama**.
- Claude uses `ANTHROPIC_MAX_TOKENS=4096` — a generous budget not limited by free-tier constraints.
- All fallback models (OpenRouter 27B, 9B) use `MAX_TOKENS_FALLBACK=1100` to stay within free-tier output caps.
- Ollama (last resort) has no token cap — `num_ctx` only.
- Added `langchain_anthropic.ChatAnthropic` lazy import inside `_get_llm()`.
- `ANTHROPIC_API_KEY` is read from env; if blank, Claude still instantiates but will fail at call time and trigger fallback — per LangChain `.with_fallbacks()` contract.

### `chat_agent.py` — Anthropic-first chat LLM
- **Rewrote `_get_chat_llm()`** to match the same Anthropic-first strategy as `_get_llm()`.
- New priority chain: **Claude → Gemini → OpenAI → OpenRouter → Ollama**.
- Claude uses `ANTHROPIC_MAX_TOKENS=4096`.
- Gemini, OpenAI, OpenRouter all use `MAX_TOKENS_FALLBACK=1100`.
- Ollama moved to **last resort** position (was first priority before — this was backwards).
- Print statement updated from `[init]` to `[ChatAgent]` for clarity in logs.
- Added `langchain_anthropic.ChatAnthropic` lazy import inside the function.
