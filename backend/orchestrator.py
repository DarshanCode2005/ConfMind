"""
orchestrator.py — LangGraph StateGraph orchestrator for ConfMind.

Wires all 8 specialized agents into a directed graph.  The orchestrator
is the single entry point for running a full conference plan.

Execution topology
──────────────────
START
  │
  ├──► venue_agent      ┐  parallel fan-out
  ├──► sponsor_agent    │  (these three run concurrently)
  └──► speaker_agent    ┘
          │
          ▼
      exhibitor_agent
          │
          ▼
      pricing_agent
          │
          ▼
      community_gtm_agent
          │
          ▼
      event_ops_agent
          │
          ▼
      revenue_agent
          │
         END

Usage
─────
    from backend.orchestrator import run_plan
    from backend.models.schemas import EventConfigInput

    config = EventConfigInput(
        category="AI",
        geography="Europe",
        audience_size=800,
        budget_usd=50_000,
        event_dates="2025-09-15",
    )
    final_state = await run_plan(config)
    print(final_state["sponsors"])

FastAPI integration
───────────────────
    from backend.orchestrator import graph   # compiled LangGraph CompiledGraph
    # Invoke synchronously in a threadpool executor or use async invoke
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph  # type: ignore[import-untyped]

from backend.models.schemas import AgentState, EventConfigInput

# ── Agent imports ─────────────────────────────────────────────────────────────
# Each agent is imported lazily here.  At scaffolding time these modules are
# stubs — teammates will fill in the logic.  Importing them here is what
# registers them in the graph.


def _import_agents() -> dict[str, Any]:
    """Import all agent instances.  Returns a dict of name -> agent instance.

    Lazy import prevents circular dependency errors during scaffolding and
    keeps startup fast when only a subset of agents are ready.
    """
    agents: dict[str, Any] = {}

    # P1 responsibility — base class only, no specialisation needed
    try:
        from backend.agents.web_search_agent import WebSearchAgent
        # Spawn 3 parallel agents per diagram
        for i in range(1, 4):
            # Stagger offsets so they fetch unique slices
            agents[f"web_search_agent_{i}"] = WebSearchAgent(agent_id=i, offset=(i-1)*10, limit=10)
    except ImportError:
        for i in range(1, 4):
            agents[f"web_search_agent_{i}"] = None

    # P2 responsibility
    try:
        from backend.agents.sponsor_agent import SponsorAgent

        agents["sponsor_agent"] = SponsorAgent()
    except ImportError:
        agents["sponsor_agent"] = None

    try:
        from backend.agents.speaker_agent import SpeakerAgent

        agents["speaker_agent"] = SpeakerAgent()
    except ImportError:
        agents["speaker_agent"] = None

    try:
        from backend.agents.exhibitor_agent import ExhibitorAgent

        agents["exhibitor_agent"] = ExhibitorAgent()
    except ImportError:
        agents["exhibitor_agent"] = None

    try:
        from backend.agents.revenue_agent import RevenueAgent

        agents["revenue_agent"] = RevenueAgent()
    except ImportError:
        agents["revenue_agent"] = None

    # P3 responsibility
    try:
        from backend.agents.venue_agent import VenueAgent

        agents["venue_agent"] = VenueAgent()
    except ImportError:
        agents["venue_agent"] = None

    try:
        from backend.agents.pricing_agent import PricingAgent

        agents["pricing_agent"] = PricingAgent()
    except ImportError:
        agents["pricing_agent"] = None

    # P5 responsibility
    try:
        from backend.agents.community_gtm_agent import CommunityGTMAgent

        agents["community_gtm_agent"] = CommunityGTMAgent()
    except ImportError:
        agents["community_gtm_agent"] = None

    try:
        from backend.agents.event_ops_agent import EventOpsAgent

        agents["event_ops_agent"] = EventOpsAgent()
    except ImportError:
        agents["event_ops_agent"] = None

    return agents


def phq_probe(state: AgentState) -> dict[str, Any]:
    """PredictHQ probe node — decides search scope and parallelism logic."""
    from backend.main import _agent_status
    plan_id = state.get("metadata", {}).get("plan_id")
    if plan_id:
        _agent_status.setdefault(str(plan_id), {})["phq_probe"] = "running"

    # Logic to Decide N agents or search windows based on config
    cfg = state["event_config"]
    # For now, we use a fixed 3 agents, but we could split by date or geography
    if plan_id:
        _agent_status.setdefault(str(plan_id), {})["phq_probe"] = "completed"

    return {
        "metadata": {
            "web_agents_count": 3,
            "search_query": f"{cfg.category} {cfg.geography}",
        }
    }


def _make_node(agent: Any, name: str):
    """Wrap an agent's run() method as a LangGraph node function.

    If the agent module hasn't been implemented yet (None), the node is a
    passthrough that writes an empty result so the graph can still compile and
    continue to the next node.
    """
    if agent is None:
        def passthrough(state: AgentState) -> dict[str, Any]:
            return {"errors": [f"[{name}] not yet implemented — skipping"]}

        passthrough.__name__ = name
        return passthrough

    def node_fn(state: AgentState) -> dict[str, Any]:
        plan_id = None
        metadata = state.get("metadata", {})
        if isinstance(metadata, dict):
            plan_id = metadata.get("plan_id")

        if plan_id:
            try:
                from backend.main import _agent_status

                _agent_status.setdefault(str(plan_id), {})[name] = "running"
            except Exception:
                pass

        try:
            result = agent.run(state)
        except Exception as exc:
            if plan_id:
                try:
                    from backend.main import _agent_status

                    _agent_status.setdefault(str(plan_id), {})[name] = "failed"
                except Exception:
                    pass
            raise exc

        if plan_id:
            try:
                from backend.main import _agent_status

                _agent_status.setdefault(str(plan_id), {})[name] = "completed"
            except Exception:
                pass

        # Ensure it returns a dict for LangGraph merging
        if isinstance(result, dict):
            return result
        return {}  # Fallback if agent returned something else

    node_fn.__name__ = name
    return node_fn


def _build_graph() -> Any:
    """Build and compile the LangGraph StateGraph.

    The graph is compiled once at module load time and reused for all requests.
    """
    agents = _import_agents()

    builder = StateGraph(AgentState)

    # 1. PHQ Probe Node
    builder.add_node("phq_probe", phq_probe)

    # 2. Register all specialized agent nodes
    for name, agent in agents.items():
        builder.add_node(name, _make_node(agent, name))

    # ── Edges ─────────────────────────────────────────────────────────────
    # START -> phq_probe -> parallel web searches
    builder.add_edge(START, "phq_probe")

    web_agents = [n for n in agents.keys() if n.startswith("web_search_agent_")]
    for wa in web_agents:
        builder.add_edge("phq_probe", wa)

    # Discovery agents (Fan-out from all web agents)
    discovery_agents = ["venue_agent", "sponsor_agent", "speaker_agent", "exhibitor_agent"]
    for wa in web_agents:
        for da in discovery_agents:
            builder.add_edge(wa, da)

    # Analytics / Strategy Pipeline
    # Pricing runs after discovery is mostly done (venue/sponsor/speaker needed)
    builder.add_edge("venue_agent", "pricing_agent")
    builder.add_edge("sponsor_agent", "pricing_agent")
    builder.add_edge("speaker_agent", "pricing_agent")

    builder.add_edge("pricing_agent", "community_gtm_agent")
    builder.add_edge("exhibitor_agent", "community_gtm_agent")

    builder.add_edge("community_gtm_agent", "event_ops_agent")
    builder.add_edge("event_ops_agent", "revenue_agent")
    builder.add_edge("revenue_agent", END)

    return builder.compile()


# Module-level compiled graph — imported by FastAPI main.py
graph = _build_graph()


def _initial_state(config: EventConfigInput, plan_id: str | None = None) -> AgentState:
    """Create a blank AgentState from the user's EventConfigInput.

    All list and dict fields are initialised to empty so agents that run first
    don't encounter KeyErrors when reading OTHER agents' fields.
    """
    return AgentState(
        event_config=config,
        past_events=[],
        sponsors=[],
        speakers=[],
        venues=[],
        exhibitors=[],
        pricing=[],
        communities=[],
        schedule=[],
        revenue={},
        gtm_messages={},
        messages=[],
        errors=[],
        metadata={"plan_id": plan_id} if plan_id else {},
    )


async def run_plan(config: EventConfigInput, plan_id: str | None = None) -> AgentState:
    """Run the full conference planning pipeline for a given EventConfigInput.

    Args:
        config: User's event configuration from the API or UI.

    Returns:
        The final AgentState with all agent outputs filled in.

    Usage::

        state = await run_plan(
            EventConfigInput(
                category="AI",
                geography="Europe",
                audience_size=800,
                budget_usd=50_000,
                event_dates="2025-09-15",
            )
        )
    """
    initial = _initial_state(config, plan_id=plan_id)
    final_state: AgentState = await graph.ainvoke(initial)  # type: ignore[assignment]
    return final_state
