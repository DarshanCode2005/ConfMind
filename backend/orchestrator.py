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
        result = agent.run(state)
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

    # Register all 8 agent nodes
    for name, agent in agents.items():
        builder.add_node(name, _make_node(agent, name))

    # ── Edges ─────────────────────────────────────────────────────────────
    # Parallel fan-out from START: venue, sponsor, speaker run simultaneously
    builder.add_edge(START, "venue_agent")
    builder.add_edge(START, "sponsor_agent")
    builder.add_edge(START, "speaker_agent")

    # After all three finish, exhibitor agent runs
    builder.add_edge("venue_agent", "exhibitor_agent")
    builder.add_edge("sponsor_agent", "exhibitor_agent")
    builder.add_edge("speaker_agent", "exhibitor_agent")

    # Linear pipeline from exhibitor onwards
    builder.add_edge("exhibitor_agent", "pricing_agent")
    builder.add_edge("pricing_agent", "community_gtm_agent")
    builder.add_edge("community_gtm_agent", "event_ops_agent")
    builder.add_edge("event_ops_agent", "revenue_agent")
    builder.add_edge("revenue_agent", END)

    return builder.compile()


# Module-level compiled graph — imported by FastAPI main.py
graph = _build_graph()


def _initial_state(config: EventConfigInput) -> AgentState:
    """Create a blank AgentState from the user's EventConfigInput.

    All list and dict fields are initialised to empty so agents that run first
    don't encounter KeyErrors when reading OTHER agents' fields.
    """
    return AgentState(
        event_config=config,
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
        metadata={},
    )


async def run_plan(config: EventConfigInput) -> AgentState:
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
    initial = _initial_state(config)
    final_state: AgentState = await graph.ainvoke(initial)  # type: ignore[assignment]
    return final_state
