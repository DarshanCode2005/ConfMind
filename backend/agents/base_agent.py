"""
base_agent.py — Abstract base class for all ConfMind agents.

Every specialized agent (Sponsor, Speaker, Venue…) inherits BaseAgent.
The orchestrator calls agent_instance.run(state) for each node in the graph.

Subclass contract
─────────────────
You MUST override:
    name: str                    — unique agent identifier used as LangGraph node name
    _build_prompt()              — returns the system ChatPromptTemplate for this agent
    run(state) -> AgentState     — main entry point; reads + writes AgentState fields

You MAY override:
    tools: list                  — LangChain tool list; defaults to []
    _get_llm()                   — returns a ChatOpenAI instance; override for custom models

Helper methods (inherited, do NOT override)
───────────────────────────────────────────
_read_memory(query, collection)  → list[dict]   similarity search in vector store
_write_memory(docs, meta, coll)  → None         embed + store in vector store
_invoke_llm(prompt_str)          → str           invoke LLM with fallback + retry
_log_error(state, msg)           → dict          append to state.errors and return
_pass_context(name)              → context mgr   logs pass start/end + enforces memory

Global Rules (enforced by BaseAgent)
────────────────────────────────────
• Every agent reads memory at start of EVERY pass, writes delta at end.
• Tavily 429: wait 3s, retry once → skip query.
• PredictHQ 401/429: switch to Tavily-only, log once.
• LLM empty: retry once (temp=0) → fallback null.
• No inter-agent tool calls ever.
• Partial output on any error — Orchestrator continues.
"""

from __future__ import annotations

import os
import time
import json
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, ClassVar

from langchain_core.prompts import ChatPromptTemplate  # type: ignore[import-untyped]

from backend.memory.vector_store import embed_and_store, similarity_search
from backend.models.schemas import AgentState


class BaseAgent(ABC):
    """Abstract base for all ConfMind specialized agents.

    Subclasses register tools, define a system prompt, and implement run().
    The LangGraph orchestrator calls run(state) as the node function.
    """

    #: Override in subclass — must be unique, used as LangGraph node name
    name: str = "base_agent"

    #: LangChain tools available to this agent's LLM (override in subclass)
    tools: ClassVar[list[Any]] = []

    #: Track pass number for logging
    _current_pass: int = 0

    # ── LLM ──────────────────────────────────────────────────────────────

    def _get_llm(self, temperature: float | None = None) -> Any:
        """Return a Chat LLM with Anthropic-first fallback chain.

        Priority:
        1. Anthropic Claude (claude-3-haiku)      — PRIMARY   (max_tokens=ANTHROPIC_MAX_TOKENS)
        2. OpenRouter: google/gemma-2-27b-it       — SECONDARY (max_tokens=MAX_TOKENS_FALLBACK)
        3. OpenRouter: google/gemma-2-9b-it        — TERTIARY  (max_tokens=MAX_TOKENS_FALLBACK)
        4. Local Ollama: confmind-planner/gemma4   — LAST RESORT (num_ctx only)

        Token caps:
        - Claude uses ANTHROPIC_MAX_TOKENS (default 4096) - generous, not free-tier limited.
        - All fallback models use MAX_TOKENS_FALLBACK (default 1100) - free-tier safe.
        """
        from langchain_anthropic import ChatAnthropic  # type: ignore[import-untyped]
        from langchain_openai import ChatOpenAI
        from langchain_ollama import ChatOllama
        from backend.config import (
            ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS,
            PRIMARY_MODEL, SECONDARY_MODEL, LOCAL_MODEL,
            MAX_TOKENS_FALLBACK, TEMPERATURE, MAX_RETRIES,
            OPENROUTER_BASE_URL, OLLAMA_NUM_CTX,
        )

        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        or_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("openrouter_key", "")
        effective_temp = temperature if temperature is not None else TEMPERATURE

        # ── 1. Primary: Anthropic Claude ─────────────────────────────────────
        # max_tokens is REQUIRED by the Anthropic API (unlike OpenAI where it is optional).
        primary_llm = ChatAnthropic(
            model=ANTHROPIC_MODEL,
            anthropic_api_key=anthropic_key,  # type: ignore[arg-type]
            temperature=effective_temp,
            max_tokens=ANTHROPIC_MAX_TOKENS,  # generous cap - Claude is primary
            max_retries=MAX_RETRIES,
        )

        # ── 2. Secondary: Gemma 2 27B via OpenRouter (free-tier cap) ─────────
        secondary_llm = ChatOpenAI(
            model=PRIMARY_MODEL,
            openai_api_key=or_key,  # type: ignore[arg-type]
            openai_api_base=OPENROUTER_BASE_URL,
            temperature=effective_temp,
            max_tokens=MAX_TOKENS_FALLBACK,  # 1100 - free-tier safe
            max_retries=MAX_RETRIES,
        )

        # ── 3. Tertiary: Gemma 2 9B via OpenRouter (free-tier cap) ───────────
        tertiary_llm = ChatOpenAI(
            model=SECONDARY_MODEL,
            openai_api_key=or_key,  # type: ignore[arg-type]
            openai_api_base=OPENROUTER_BASE_URL,
            temperature=effective_temp,
            max_tokens=MAX_TOKENS_FALLBACK,  # 1100 - free-tier safe
            max_retries=MAX_RETRIES,
        )

        # ── 4. Last resort: Local Ollama (always available offline) ──────────
        local_llm = ChatOllama(
            model=LOCAL_MODEL,
            temperature=effective_temp,
            num_ctx=OLLAMA_NUM_CTX,
        )

        # Build fallback chain: Claude -> OR 27B -> OR 9B -> Ollama
        llm = primary_llm.with_fallbacks([secondary_llm, tertiary_llm, local_llm])

        if self.tools:
            return llm.bind_tools(self.tools)
        return llm

    # ── LLM invocation with retry ─────────────────────────────────────────

    def _invoke_llm(self, prompt_str: str, temperature: float = 0.3) -> str:
        """Invoke LLM with retry logic per spec.

        - First attempt at given temperature.
        - If empty response: retry once at temp=0.
        - If still empty: return "null" fallback.
        """
        llm = self._get_llm(temperature=temperature)
        try:
            response = llm.invoke(prompt_str)
            content = response.content if hasattr(response, 'content') else str(response)
            if content and content.strip():
                return content.strip()
            # Retry once at temp=0
            self._log_info("LLM returned empty, retrying at temp=0...")
            llm_retry = self._get_llm(temperature=0)
            response = llm_retry.invoke(prompt_str)
            content = response.content if hasattr(response, 'content') else str(response)
            if content and content.strip():
                return content.strip()
        except Exception as e:
            self._log_info(f"LLM invocation failed: {e}")
        return "null"

    def _invoke_llm_json(self, prompt_str: str, temperature: float = 0.1) -> Any:
        """Invoke LLM expecting JSON output. Parse and return Python object."""
        import re
        raw = self._invoke_llm(prompt_str, temperature=temperature)
        if raw == "null":
            return None
        # Strip markdown code fences
        text = re.sub(r"```(?:json)?\s*", "", raw)
        text = re.sub(r"```", "", text)
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON within the text
            for start_char in ["[", "{"]:
                idx = text.find(start_char)
                if idx != -1:
                    try:
                        return json.loads(text[idx:])
                    except json.JSONDecodeError:
                        pass
        self._log_info(f"Could not parse LLM JSON output: {raw[:200]}")
        return None

    # ── Prompt ────────────────────────────────────────────────────────────

    @abstractmethod
    def _build_prompt(self) -> ChatPromptTemplate:
        """Return the system + human ChatPromptTemplate for this agent.

        The prompt must include at least:
          - A system message describing the agent's role
          - A human message placeholder: ("human", "{input}")
        """

    # ── Main entry point ──────────────────────────────────────────────────

    @abstractmethod
    def run(self, state: AgentState) -> dict[str, Any]:
        """Execute the agent's logic and return a delta dict for LangGraph merging.

        Args:
            state: The full shared LangGraph state. Read inputs from other
                   fields (e.g. state["event_config"]) and write outputs into
                   the field(s) this agent owns (e.g. state["sponsors"]).

        Returns:
            A dict containing ONLY the keys this agent modifies.

        Error handling:
            Catch ALL exceptions and call self._log_error(state, str(e)) so
            the orchestrator can continue with other agents even if this one fails.
        """

    # ── Pass context manager ──────────────────────────────────────────────

    @contextmanager
    def _pass_context(self, pass_name: str, state: AgentState, memory_query: str | None = None):
        """Context manager that enforces memory read at start and tracks pass.

        Usage:
            with self._pass_context("Pass 1: Extract", state, "sponsors for AI conferences"):
                # ... agent logic ...

        This reads memory at entry, logs pass boundaries, and increments pass counter.
        """
        self._current_pass += 1
        self._log_info(f"── {pass_name} (pass {self._current_pass}) ──")

        # Mandatory memory read at start of every pass
        memory_context = []
        if memory_query:
            try:
                memory_context = self._read_memory(memory_query, collection=self.name)
            except Exception:
                pass  # Memory read failure is non-fatal

        if memory_context:
            self._log_info(f"  Memory provided {len(memory_context)} context items")

        yield memory_context

    # ── Memory helpers ───────────────────────────────────────────────────

    def _read_memory(
        self,
        query: str,
        collection: str = "events",
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve k similar documents from the vector store.

        Args:
            query:      Natural language query string.
            collection: ChromaDB/Pinecone collection name (default "events").
            k:          Number of results to return.

        Returns:
            List of dicts with 'document' and 'metadata' keys.
        """
        return similarity_search(query, collection=collection, k=k)

    def _write_memory(
        self,
        docs: list[str],
        metadata: list[dict[str, Any]],
        collection: str = "events",
    ) -> None:
        """Embed and store documents into the vector store (append-only).

        Args:
            docs:       List of text strings to embed.
            metadata:   Parallel list of metadata dicts (same length as docs).
            collection: Target ChromaDB/Pinecone collection.
        """
        if not docs:
            return
        try:
            embed_and_store(docs, metadata, collection=collection)
            self._log_info(f"  Wrote {len(docs)} items to memory [{collection}]")
        except Exception as e:
            self._log_info(f"  Memory write failed (non-fatal): {e}")

    def index_to_chroma(
        self,
        documents: list[str],
        collection: str,
        metadata: list[dict[str, Any]],
    ) -> None:
        """Contract: Index agent output to ChromaDB for the Chat Agent.
        
        Args:
            documents: List of formatted text strings.
            collection: The ChromaDB collection (e.g., 'chat_index').
            metadata: List of metadata dicts for filtering (must include 'agent').
        """
        try:
            embed_and_store(documents, metadata, collection=collection)
            self._log_info(f"  Indexed {len(documents)} objects to ChromaDB [{collection}]")
        except Exception as e:
            self._log_info(f"  ChromaDB indexing failed: {e}")


    # ── Tavily helper with retry ──────────────────────────────────────────

    def _tavily_search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Execute a Tavily search with spec-compliant retry logic.

        - search_depth="advanced", max_results=5
        - Only use the "content" field
        - On 429: wait 3s, retry once → return empty list
        """
        try:
            from tavily import TavilyClient  # type: ignore[import-untyped]
        except ImportError:
            self._log_info("Tavily not installed, skipping search")
            return []

        api_key = os.getenv("TAVILY_API_KEY", "")
        if not api_key:
            self._log_info("TAVILY_API_KEY not set, skipping search")
            return []

        client = TavilyClient(api_key=api_key)

        for attempt in range(2):
            try:
                response = client.search(
                    query=query,
                    search_depth="advanced",
                    max_results=max_results,
                )
                results = response.get("results", [])
                # Return only the content field per spec
                return [{"content": r.get("content", ""), "url": r.get("url", "")} for r in results]
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate" in err_str:
                    if attempt == 0:
                        self._log_info("Tavily 429 — waiting 3s before retry...")
                        time.sleep(3)
                        continue
                    else:
                        self._log_info("Tavily 429 — retry exhausted, skipping query")
                        return []
                else:
                    self._log_info(f"Tavily search failed: {e}")
                    return []

        return []

    # ── Logging helpers ───────────────────────────────────────────────────

    def _log_info(self, message: str) -> None:
        """Print a formatted log message for real-time monitoring."""
        print(f"  [DEBUG][{self.name}] {message}")

    def _log_error(self, state: Any, message: str) -> dict[str, Any]:
        """Return a delta dict with the error message for LangGraph merging."""
        msg = f"[{self.name}] {message}"
        print(f"  [ERROR] {msg}")
        return {"errors": [msg]}

    # ── String representation ─────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} tools={len(self.tools)}>"
