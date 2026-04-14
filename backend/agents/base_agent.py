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
_log_error(state, msg)           → AgentState   append to state.errors and return

Usage example (in a subclass)
─────────────────────────────
    class SponsorAgent(BaseAgent):
        name = "sponsor_agent"

        def _build_prompt(self) -> ChatPromptTemplate:
            return ChatPromptTemplate.from_messages([
                ("system", "You are a sponsor discovery specialist..."),
                ("human", "{input}"),
            ])

        def run(self, state: AgentState) -> AgentState:
            cfg = state["event_config"]
            # ... call tools, produce sponsors ...
            state["sponsors"] = ranked_sponsors
            return state
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
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

    # ── LLM ──────────────────────────────────────────────────────────────
    
    def _get_llm(self, temperature: float = 0.3) -> Any:
        """Return a ChatOllama instance (local Gemma4) bound to this agent's tools.

        Uses the 'confmind-gemma4' model installed in Ollama.
        """
        from langchain_ollama import ChatOllama  # type: ignore[import-untyped]

        model_name = os.getenv("OLLAMA_MODEL", "confmind-planner")
        llm = ChatOllama(
            model=model_name,
            temperature=temperature,
            num_ctx=32768,  # Sufficient for most planning tasks
        )
        if self.tools:
            return llm.bind_tools(self.tools)
        return llm

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
    def run(self, state: AgentState) -> AgentState:
        """Execute the agent's logic and return the updated AgentState.

        Args:
            state: The full shared LangGraph state.  Read inputs from other
                   fields (e.g. state["event_config"]) and write outputs into
                   the field(s) this agent owns (e.g. state["sponsors"]).

        Returns:
            The updated AgentState dict with this agent's output filled in.

        Error handling:
            Catch ALL exceptions and call self._log_error(state, str(e)) so
            the orchestrator can continue with other agents even if this one fails.

        Example::

            def run(self, state: AgentState) -> AgentState:
                try:
                    cfg = state["event_config"]
                    sponsors = search_sponsors_structured(cfg.category, cfg.geography)
                    state["sponsors"] = sponsors
                except Exception as exc:
                    state = self._log_error(state, str(exc))
                return state
        """

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
        """Embed and store documents into the vector store.

        Args:
            docs:       List of text strings to embed.
            metadata:   Parallel list of metadata dicts (same length as docs).
            collection: Target ChromaDB/Pinecone collection.
        """
        embed_and_store(docs, metadata, collection=collection)

    # ── Logging helpers ───────────────────────────────────────────────────

    def _log_info(self, message: str) -> None:
        """Print a formatted log message for real-time monitoring."""
        print(f"  [DEBUG][{self.name}] {message}")

    def _log_error(self, state: AgentState, message: str) -> dict[str, Any]:
        """Return a delta dict with the error message for LangGraph merging."""
        msg = f"[{self.name}] {message}"
        print(f"  [ERROR] {msg}")
        return {"errors": [msg]}

    # ── String representation ─────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} tools={len(self.tools)}>"
