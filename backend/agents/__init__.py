"""
ConfMind Agent Definitions

All specialized agents for the ConfMind multi-agent event planning system.
Each agent inherits from BaseAgent and implements the run() + _build_prompt() contract.

Architecture (per spec):
    Orchestrator → [N × WebSearch] → Shared Memory →
      [Sponsor ∥ Speaker ∥ Venue] → Exhibitor →
      [Pricing ∥ GTM] → EventOps → Revenue
"""

from backend.agents.base_agent import BaseAgent
from backend.agents.web_search_agent import WebSearchAgent
from backend.agents.sponsor_agent import SponsorAgent
from backend.agents.speaker_agent import SpeakerAgent
from backend.agents.venue_agent import VenueAgent
from backend.agents.exhibitor_agent import ExhibitorAgent
from backend.agents.pricing_agent import PricingAgent
from backend.agents.community_gtm_agent import CommunityGTMAgent
from backend.agents.event_ops_agent import EventOpsAgent
from backend.agents.revenue_agent import RevenueAgent

__all__ = [
    "BaseAgent",
    "WebSearchAgent",
    "SponsorAgent",
    "SpeakerAgent",
    "VenueAgent",
    "ExhibitorAgent",
    "PricingAgent",
    "CommunityGTMAgent",
    "EventOpsAgent",
    "RevenueAgent",
]
