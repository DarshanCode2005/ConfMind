"""
community_gtm_agent.py — Community & Go-To-Market Agent for ConfMind.

System Prompt:
  "You are the Community & GTM Agent. Focus on Discord first."

Loop (5 passes):
  • Pass 1-2: 5 parallel Tavily queries for Discord/Slack/LinkedIn/
              Facebook/Reddit.
  • Pass 3: LLM niche categorization + relevance score.
  • Pass 4: PredictHQ Events (upcoming, rank>70) → timing.
  • Pass 5: Generate 3 message variants per channel.

Stop: ≥10 communities.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState, CommunitySchema

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_TARGET_COMMUNITIES = 10
_PLATFORMS = ["Discord", "Slack", "LinkedIn", "Facebook", "Reddit"]
_MESSAGES_PER_CHANNEL = 3


class CommunityGTMAgent(BaseAgent):
    """Discovers communities and generates GTM outreach messages.

    Sources:
        1. Tavily for community discovery across 5 platforms
        2. LLM for niche categorization + relevance scoring
        3. PredictHQ for timing optimization
        4. LLM for message variant generation

    Output:
        state["communities"]   — list of CommunitySchema
        state["gtm_messages"]  — platform → list of message variants
    """

    name: str = "community_gtm_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are the Community & GTM Agent for ConfMind. You focus on "
                    "Discord first, then expand to other platforms.\n\n"
                    "CRITICAL RULES:\n"
                    "1. Discord communities take priority — discover these first.\n"
                    "2. Then expand to Slack, LinkedIn Groups, Facebook Groups, Reddit.\n"
                    "3. Each community gets a niche categorization and relevance score (0-10).\n"
                    "4. Use PredictHQ timing data to suggest optimal posting windows.\n"
                    "5. Generate 3 message variants per channel — different tone/angle.\n"
                    "6. Messages should be platform-native (e.g., Discord uses embeds, "
                    "Reddit uses post format, LinkedIn uses professional tone).\n"
                    "7. Target: ≥10 communities total.\n"
                    "8. NEVER make up community names or member counts.\n"
                    "9. Output valid JSON when asked.",
                ),
                ("human", "{input}"),
            ]
        )

    # ── Pass 1-2: Community discovery ─────────────────────────────────────

    def _discover_communities(self, category: str, geography: str) -> list[dict[str, Any]]:
        """Discover communities across 5 platforms via Tavily."""
        communities = []

        # Prioritized queries (Discord first per spec)
        queries = {
            "Discord": f"{category} Discord server community join {geography}",
            "Slack": f"{category} Slack workspace community join",
            "LinkedIn": f"{category} LinkedIn group professional community {geography}",
            "Facebook": f"{category} Facebook group community events",
            "Reddit": f"reddit r/{category.lower().replace(' ', '')} subreddit community",
        }

        for platform, query in queries.items():
            self._log_info(f"  Searching for {platform} communities...")
            results = self._tavily_search(query, max_results=3)

            for r in results:
                url = r.get("url", "")
                content = r.get("content", "")

                # Basic validation — check URL contains platform hint
                url_lower = url.lower()
                detected_platform = platform
                for p in _PLATFORMS:
                    if p.lower() in url_lower:
                        detected_platform = p
                        break

                # Extract community name from content
                name = content[:80].split(".")[0].strip() if content else url
                if not name or len(name) < 3:
                    name = f"{category} {detected_platform} Community"

                communities.append({
                    "name": name,
                    "platform": detected_platform,
                    "invite_url": url,
                    "content": content[:500],
                    "niche": "",
                    "relevance": 0.0,
                    "size": 0,
                })

        self._log_info(f"Discovered {len(communities)} communities across {len(queries)} platforms")
        return communities

    # ── Pass 3: LLM categorization + scoring ─────────────────────────────

    def _categorize_communities(
        self, communities: list[dict], category: str
    ) -> list[dict]:
        """Use LLM to assign niche categories and relevance scores."""
        if not communities:
            return communities

        # Batch categorization
        community_list = "\n".join(
            f"- {c['name']} ({c['platform']}): {c['content'][:100]}"
            for c in communities[:20]
        )

        cat_prompt = (
            f"Categorize each community by niche and rate relevance (0-10) "
            f"for a {category} event.\n\n"
            f"Communities:\n{community_list}\n\n"
            f"Niche categories: professional, hobbyist, academic, industry, "
            f"regional, general, niche_specific\n\n"
            f"Output as JSON array:\n"
            f"[{{\"name\": \"...\", \"niche\": \"...\", \"relevance\": 7.5, "
            f"\"estimated_size\": 5000}}]\n\n"
            f"Output ONLY valid JSON."
        )
        results = self._invoke_llm_json(cat_prompt)

        if results and isinstance(results, list):
            result_map = {r.get("name", ""): r for r in results if isinstance(r, dict)}
            for community in communities:
                match = result_map.get(community["name"])
                if match:
                    community["niche"] = match.get("niche", "general")
                    community["relevance"] = min(10.0, float(match.get("relevance", 5.0)))
                    community["size"] = int(match.get("estimated_size", 0))
                else:
                    community["niche"] = "general"
                    community["relevance"] = 5.0

        return communities

    # ── Pass 4: PredictHQ timing ─────────────────────────────────────────

    def _get_posting_timing(self, geography: str) -> dict[str, Any]:
        """Use PredictHQ to find upcoming high-rank events for timing."""
        timing_info = {
            "optimal_posting_window": "2-4 weeks before event date",
            "high_rank_events": [],
            "recommended_cadence": "3x/week across top platforms",
        }

        try:
            from predicthq import Client  # type: ignore[import-untyped]

            api_key = os.getenv("PREDICTHQ_API_KEY", "")
            if not api_key:
                return timing_info

            phq = Client(access_token=api_key)
            events_result = phq.events.search(
                q=geography if geography else None,
                active__gte="2025-06-01",
                rank__gte=70,
                limit=5,
            )
            for event in events_result:
                timing_info["high_rank_events"].append({
                    "title": getattr(event, "title", ""),
                    "start": str(getattr(event, "start", "")),
                    "rank": getattr(event, "rank", 0),
                })

            if timing_info["high_rank_events"]:
                self._log_info(f"Found {len(timing_info['high_rank_events'])} high-rank events for timing")

        except Exception as e:
            self._log_info(f"PredictHQ timing fetch failed: {e}")

        return timing_info

    # ── Pass 5: Message generation ────────────────────────────────────────

    def _generate_messages(
        self,
        communities: list[dict],
        category: str,
        geography: str,
        event_name: str,
        timing: dict,
    ) -> dict[str, list[str]]:
        """Generate 3 message variants per platform."""
        gtm_messages: dict[str, list[str]] = {}

        # Get unique platforms from top communities
        platforms = list(set(c["platform"] for c in communities))[:5]

        for platform in platforms:
            # Platform-specific messaging guidance
            platform_guidance = {
                "Discord": "Use casual tone, emoji, consider embed format. Keep it concise.",
                "Slack": "Professional but friendly. Include relevant hashtags/channels.",
                "LinkedIn": "Formal, value-driven. Highlight professional development.",
                "Facebook": "Engaging, visual language. Include CTA for event page.",
                "Reddit": "Informative, community-first. No spam — add value.",
            }

            relevant_communities = [c for c in communities if c["platform"] == platform]
            community_names = ", ".join(c["name"] for c in relevant_communities[:3])

            msg_prompt = (
                f"Write 3 different outreach message variants for promoting "
                f"'{event_name}' (a {category} event in {geography}) on {platform}.\n\n"
                f"Target communities: {community_names}\n"
                f"Platform guidance: {platform_guidance.get(platform, 'Keep it appropriate')}\n"
                f"Timing context: {timing.get('optimal_posting_window', '2-4 weeks out')}\n\n"
                f"Requirements:\n"
                f"1. Each variant should have a DIFFERENT angle:\n"
                f"   - Variant 1: Value proposition (why attend)\n"
                f"   - Variant 2: Social proof / FOMO (who's speaking, who attended)\n"
                f"   - Variant 3: Community angle (networking, learning together)\n"
                f"2. Include a clear CTA in each.\n"
                f"3. Keep platform-native formatting.\n\n"
                f"Output ONLY valid JSON formatted EXACTLY like this:\n"
                f"{{\"messages\": [\"message 1\", \"message 2\", \"message 3\"]}}"
            )
            data = self._invoke_llm_json(msg_prompt)
            if data and isinstance(data, dict) and "messages" in data:
                messages = data["messages"]
                if isinstance(messages, list):
                    gtm_messages[platform] = [str(m) for m in messages[:_MESSAGES_PER_CHANNEL]]
            else:
                gtm_messages[platform] = [f"Join us at {event_name} in {geography}!"]

        return gtm_messages

    # ── Main run ──────────────────────────────────────────────────────────

    def run(self, state: AgentState) -> dict[str, Any]:
        """Execute the 5-pass community & GTM pipeline."""
        self._current_pass = 0
        self._log_info("Starting community & GTM discovery run...")

        try:
            cfg = state["event_config"]
            category = cfg.category
            geography = cfg.geography
            event_name = cfg.event_name or f"{category} Summit"

            # ── Pass 1-2: Community discovery ─────────────────────────────
            with self._pass_context(
                "Pass 1-2: Community discovery", state,
                f"communities for {category}"
            ):
                communities = self._discover_communities(category, geography)

            # ── Pass 3: LLM categorization + scoring ─────────────────────
            with self._pass_context(
                "Pass 3: LLM categorization", state,
                f"categorizing {len(communities)} communities"
            ):
                communities = self._categorize_communities(communities, category)

            # Sort by relevance
            communities.sort(key=lambda c: c.get("relevance", 0), reverse=True)

            # ── Pass 4: PredictHQ timing ──────────────────────────────────
            with self._pass_context(
                "Pass 4: PredictHQ timing", state,
                f"event timing for {geography}"
            ):
                timing = self._get_posting_timing(geography)

            # ── Pass 5: Message generation ────────────────────────────────
            with self._pass_context(
                "Pass 5: Message generation", state,
                f"GTM messages for {event_name}"
            ):
                gtm_messages = self._generate_messages(
                    communities, category, geography, event_name, timing
                )

            # ── Build output CommunitySchema list ─────────────────────────
            community_schemas = []
            for c in communities[:_TARGET_COMMUNITIES]:
                community_schemas.append(CommunitySchema(
                    platform=c.get("platform", "Other"),
                    name=c.get("name", "Unknown"),
                    size=max(0, int(c.get("size", 0))),
                    niche=c.get("niche", "general"),
                    invite_url=c.get("invite_url", ""),
                ))

            # Write to memory
            docs = [f"Community: {c.name} | {c.platform} | Niche: {c.niche}" for c in community_schemas]
            meta = [{"name": c.name, "platform": c.platform} for c in community_schemas]
            self._write_memory(docs, meta, collection="events")

            self._log_info(f"Completed — {len(community_schemas)} communities, {len(gtm_messages)} platform messages")

            return {
                "communities": community_schemas,
                "gtm_messages": gtm_messages,
                "metadata": {"gtm_timing": timing},
            }

        except Exception as exc:
            return self._log_error(state, f"CommunityGTMAgent failed: {exc}")
