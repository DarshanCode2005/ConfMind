"""
community_gtm_agent.py — Go-to-Market and community outreach agent for ConfMind.

Finds relevant online communities (Discord, Slack, Reddit) and generates
tailored outreach messages for each platform.
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState, CommunitySchema
from backend.tools.serper_tool import search_communities

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_TOP_N = 5


class CommunityGTMAgent(BaseAgent):
    """Discovers distribution channels and drafts GTM messages."""

    name: str = "community_gtm_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a GTM (Go-To-Market) strategist for tech conferences. "
                    "You identify the best online communities to promote an event "
                    "and write compelling, platform-specific invitation messages.",
                ),
                ("human", "Event: {event_name} in {city}. Category: {category}. Platform: {platform}."),
            ]
        )

    def run(self, state: AgentState) -> AgentState:
        try:
            cfg = state["event_config"]
            category = cfg.category
            geo = cfg.geography
            event_name = cfg.event_name or f"{category} Summit"

            # ── 1. Search for communities ─────────────────────────────────────
            serper_results = search_communities(category)
            communities: list[CommunitySchema] = []

            for r in serper_results[:_TOP_N]:
                # Identify platform from URL or title
                url = r.url.lower()
                platform = "Other"
                if "discord" in url: platform = "Discord"
                elif "slack" in url: platform = "Slack"
                elif "reddit" in url: platform = "Reddit"
                elif "telegram" in url: platform = "Telegram"
                
                communities.append(CommunitySchema(
                    name=r.title,
                    platform=platform,
                    invite_url=r.url,
                    niche=category
                ))

            # ── 2. Generate GTM Messages ──────────────────────────────────────
            # We'll generate messages for the top 3 platforms found
            llm = self._get_llm()
            prompt = self._build_prompt()
            gtm_messages = {}

            platforms_to_message = sorted(list(set(c.platform for c in communities)))[:3]
            for p in platforms_to_message:
                chain = prompt | llm
                response = chain.invoke({
                    "event_name": event_name,
                    "city": geo,
                    "category": category,
                    "platform": p
                })
                gtm_messages[p] = response.content if hasattr(response, 'content') else str(response)

            # ── 3. Write results ──────────────────────────────────────────────
            return {
                "communities": communities,
                "gtm_messages": gtm_messages
            }

        except Exception as exc:
            return self._log_error({}, f"CommunityGTMAgent failed: {exc}")
