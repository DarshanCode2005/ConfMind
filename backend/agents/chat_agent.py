"""
chat_agent.py — Standalone Chat Agent for ConfMind.

Runs as a conversational assistant allowing users to query the generated
plan via the chat_index in Chroma, and trigger reruns of specific nodes.
"""

from __future__ import annotations

import os
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from backend.memory.vector_store import similarity_search
from backend.tools.tavily_tool import find_contact_info
from backend.models.schemas import AgentState, ChatState

# Shared in-memory mock Redis state for ChatState
_chat_cache: dict[str, ChatState] = {}

def _get_chat_llm(temperature: float = 0.0) -> Any:
    """Return a Chat LLM for the chat interface with Anthropic-first priority.

    Priority:
    1. Anthropic Claude (claude-3-haiku)  — PRIMARY   (max_tokens=ANTHROPIC_MAX_TOKENS)
    2. Gemini 1.5-flash                   — SECONDARY (max_tokens=MAX_TOKENS_FALLBACK)
    3. OpenAI gpt-4o-mini                 — TERTIARY  (max_tokens=MAX_TOKENS_FALLBACK)
    4. OpenRouter (gemma-2-9b-it)         — QUATERNARY (max_tokens=MAX_TOKENS_FALLBACK)
    5. Ollama (local)                     — LAST RESORT

    Token caps:
    - Claude: ANTHROPIC_MAX_TOKENS (default 4096) - primary, not free-tier limited.
    - All others: MAX_TOKENS_FALLBACK (default 1100) - free-tier safe.
    """
    from langchain_anthropic import ChatAnthropic  # type: ignore[import-untyped]
    from backend.config import (
        ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS,
        SECONDARY_MODEL, LOCAL_MODEL,
        MAX_TOKENS_FALLBACK, OPENROUTER_BASE_URL, OLLAMA_NUM_CTX,
    )

    candidates: list[tuple[str, Any]] = []

    # 1. Anthropic Claude — always try first if key is present
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        try:
            candidates.append((
                f"Anthropic ({ANTHROPIC_MODEL})",
                ChatAnthropic(
                    model=ANTHROPIC_MODEL,
                    anthropic_api_key=anthropic_key,  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=ANTHROPIC_MAX_TOKENS,  # generous, not capped at 1100
                ),
            ))
        except Exception:
            pass

    # 2. Gemini — fallback if Anthropic fails
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        candidates.append((
            "Gemini (1.5-flash)",
            ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=gemini_key,
                temperature=temperature,
                max_output_tokens=MAX_TOKENS_FALLBACK,  # free-tier cap
            ),
        ))

    # 3. OpenAI — fallback
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        candidates.append((
            "OpenAI (gpt-4o-mini)",
            ChatOpenAI(
                model="gpt-4o-mini",
                openai_api_key=openai_key,
                temperature=temperature,
                max_tokens=MAX_TOKENS_FALLBACK,  # free-tier cap
            ),
        ))

    # 4. OpenRouter — fallback
    or_key = os.getenv("OPENROUTER_API_KEY", "")
    if or_key:
        candidates.append((
            f"OpenRouter ({SECONDARY_MODEL})",
            ChatOpenAI(
                model=SECONDARY_MODEL,
                openai_api_key=or_key,
                openai_api_base=OPENROUTER_BASE_URL,
                temperature=temperature,
                max_tokens=MAX_TOKENS_FALLBACK,  # free-tier cap
            ),
        ))

    # 5. Ollama — last resort (no token cap — local model)
    if os.getenv("USE_OLLAMA", "false").lower() == "true":
        try:
            candidates.append((
                f"Ollama ({LOCAL_MODEL})",
                ChatOllama(
                    model=LOCAL_MODEL,
                    temperature=temperature,
                    num_ctx=OLLAMA_NUM_CTX,
                ),
            ))
        except Exception:
            pass

    if not candidates:
        # Emergency default — should never happen in a properly configured environment
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=temperature,
            max_tokens=MAX_TOKENS_FALLBACK,
        )

    primary_name, primary_llm = candidates[0]
    print(f"--- [ChatAgent] Primary LLM: {primary_name} ---")

    fallbacks = [c[1] for c in candidates[1:]]
    if fallbacks:
        return primary_llm.with_fallbacks(fallbacks)
    return primary_llm

def get_chat_state(session_id: str) -> ChatState:
    if session_id not in _chat_cache:
        _chat_cache[session_id] = {
            "chat_history": [],
            "run_id": "",
            "current_summary": "No current plan overview available.",
            "pending_rerun": None,
        }
    return _chat_cache[session_id]


class ChatAgentHost:
    """Hosts the React Agent for the POST /chat endpoint."""

    async def invoke(self, session_id: str, message: str, plan_id: str | None = None) -> str:
        state = get_chat_state(session_id)
        if plan_id:
            state["run_id"] = plan_id

        # Bind tools to this specific session state
        @tool
        def get_summary() -> str:
            """Fetch the distilled context/summary of the current conference plan being worked on."""
            return state.get("current_summary", "No current plan overview available.")

        @tool
        async def trigger_rerun(node_names: list[str]) -> str:
            """Trigger a re-execution of specific agents.
            Example node names: ['speaker_agent', 'venue_agent'] or ['all'].
            """
            state["pending_rerun"] = node_names
            return f"Triggered rerun for {node_names}. The backend will handle the execution."

        @tool
        def retrieve(query: str, agent_filter: str | None = None) -> str:
            """Retrieve relevant context from the chat_index about the generated plan.
            Use agent_filter to restrict to one of: 'sponsor', 'speaker', 'venue', 'pricing', 'community_gtm', 'event_ops', 'web_search', 'exhibitor', 'revenue'.
            """
            agents_list = [agent_filter] if agent_filter else None
            results = similarity_search(query, k=5, collection="chat_index", agents=agents_list)
            docs = [f"--- Result ---\n{r['document']}\nMetadata: {r['metadata']}" for r in results]
            return "\n\n".join(docs)

        @tool
        async def update_plan_parameter(field: str, value: Any) -> str:
            """Update a specific parameter in the conference plan's event configuration.
            Valid fields: category, geography, audience_size, budget_usd, event_dates, event_name.
            Example: update_plan_parameter('geography', 'London')
            """
            if "pending_updates" not in state:
                state["pending_updates"] = {} # type: ignore
            state["pending_updates"][field] = value # type: ignore
            return f"Updated {field} to {value}. This will be applied in the next rerun."

        @tool
        def draft_outreach_email(name: str, type: str) -> str:
            """
            Draft a personalized outreach email for a sponsor or speaker.
            If info is missing from knowledge base, it searches the web via Tavily.
            
            Args:
                name: Full name of the sponsor company or speaker.
                type: Either 'sponsor' or 'speaker'.
            """
            import os
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage
            
            # 1. Look in RAG
            results = similarity_search(name, collection=f"{type}s", k=3)
            context = ""
            if results:
                context = "\n".join([r['document'] for r in results])
            
            # 2. Look for email/contact via Tavily
            contact_info = find_contact_info(name, type)
            
            # 3. Draft the email
            llm = _get_chat_llm(temperature=0.7)
            prompt = (
                f"You are a professional conference organizer. Task: Draft a custom outreach email for {name} ({type}).\n\n"
                f"Context from project knowledge base: {context}\n\n"
                f"Contact information / web snippets found: {contact_info}\n\n"
                f"Write a compelling, professional, and personalized email. Include a placeholder for the sender name.\n"
                f"At the TOP, display the 'Recipient Address' (if an email was found, use it; otherwise say 'Contact via [URL]').\n"
                f"Then output the full email draft."
            )
            
            res = llm.invoke([HumanMessage(content=prompt)])
            return str(res.content)

        tools = [retrieve, trigger_rerun, get_summary, draft_outreach_email, update_plan_parameter]
        llm = _get_chat_llm(temperature=0)

        system_prompt = SystemMessage(
            content=(
                "You are the ConfMind conversational assistant. You help users understand and modify their conference plan. "
                "You DO NOT have direct access to the plan state. You MUST use tools to fetch data from the vector db (retrieve). "
                "If the user wants to change something (e.g. 'Change city to London'), use 'update_plan_parameter' to set the new value, "
                "and then 'trigger_rerun' for the relevant agents (e.g. ['venue_agent']). "
                "Always confirm to the user what you have updated and what rerun you triggered."
            )
        )

        messages = [system_prompt]
        # Rehydrate history
        for msg in state["chat_history"]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=message))

        agent = create_react_agent(llm, tools)
        result = await agent.ainvoke({"messages": messages})

        last_msg = result["messages"][-1]
        ai_msg = getattr(last_msg, "content", "")

        # Update chat history
        state["chat_history"].append({"role": "user", "content": message})
        state["chat_history"].append({"role": "assistant", "content": str(ai_msg)})

        # Generate summary (lighter summary for history context)
        summary_prompt = (
            f"Summarize the current working state of the conference plan in 2-3 sentences based on this latest interaction:\n"
            f"User: {message}\nAssistant: {ai_msg}"
        )
        summary_res = await llm.ainvoke([HumanMessage(content=summary_prompt)])
        if isinstance(summary_res, AIMessage):
            state["current_summary"] = str(getattr(summary_res, "content", ""))

        return str(ai_msg)


async def generate_workflow_completion_summary(plan_id: str, plan_data: dict[str, Any]) -> None:
    """Generate and cache the current_summary in ChatState after full workflow completion."""
    try:
        cfg = plan_data.get("event_config", {})
        eb_name = cfg.get("event_name") or f"{cfg.get('category')} Summit"
        rev = plan_data.get("revenue", {})
        total_rev = rev.get("total_projected_revenue", 0.0)

        venues = plan_data.get("venues", []) or []
        top_venues_list = []
        for v in venues[:2]:
            if isinstance(v, dict):
                top_venues_list.append(v.get("name", "Unknown Venue"))
            else:
                top_venues_list.append(getattr(v, "name", "Unknown Venue"))
        top_venues = ", ".join(top_venues_list)
        
        speakers = plan_data.get("speakers", []) or []
        top_speakers_list = []
        for s in speakers[:3]:
            if isinstance(s, dict):
                top_speakers_list.append(s.get("name", "Unknown Speaker"))
            else:
                top_speakers_list.append(getattr(s, "name", "Unknown Speaker"))
        top_speakers = ", ".join(top_speakers_list)

        v_example = top_venues_list[0] if top_venues_list else "XYZ"
        s_example = top_speakers_list[0] if top_speakers_list else "ABC"

        prompt = (
            f"You are the ConfMind conversational assistant.\n"
            f"A conference plan for '{eb_name}' has been successfully built.\n"
            f"Top Venues selected: {top_venues}\n"
            f"Top Speakers ranked: {top_speakers}\n"
            f"Projected total revenue: ${total_rev:,.2f}.\n\n"
            f"Please write an engaging opening message (2-3 paragraphs) directed at the user. "
            f"Summarize the plan's readiness and offer proactive, specific strategic suggestions based on the provided names. "
            f"For example: 'Venue {v_example} looks great as it has hosted successful events, and you should try approaching speaker {s_example} because they are trending.' "
        )

        llm = _get_chat_llm(temperature=0)
        res = await llm.ainvoke([HumanMessage(content=prompt)])

        if isinstance(res, AIMessage):
            chat_state = get_chat_state(plan_id)
            chat_state["run_id"] = plan_id
            
            content = str(getattr(res, "content", ""))
            if len(chat_state["chat_history"]) == 0:
                chat_state["chat_history"].append({"role": "assistant", "content": content})
                
            chat_state["current_summary"] = content
    except Exception as e:
        logging.error(f"Failed to generate completion summary: {e}")


chat_agent_host = ChatAgentHost()
