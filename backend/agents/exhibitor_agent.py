"""
exhibitor_agent.py — Exhibitor clustering agent for ConfMind.

System Prompt:
  "You are the Exhibitor Agent. Cluster only — no discovery."

Loop (3 passes):
  • Pass 1: Extract from past_events.
  • Pass 2: LLM multi-label cluster (startup/enterprise/tools_platform/
            media/individual/government).
  • Pass 3: Gap-fill max 3 Tavily queries for empty clusters.

Stop: All clusters ≥1 or 1 round done.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState, ExhibitorSchema

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_CLUSTER_LABELS = [
    "startup",
    "enterprise",
    "tools_platform",
    "media",
    "individual",
    "government",
]


class ExhibitorAgent(BaseAgent):
    """Extracts and clusters exhibitors from past_events.

    This agent does NOT do new discovery — it works only from data already
    gathered by the WebSearchAgent and stored in past_events.

    Sources:
        1. past_events exhibitor lists
        2. LLM for multi-label clustering
        3. Tavily gap-fill for empty clusters (max 3 queries)

    Output:
        state["exhibitors"] — list of ExhibitorSchema with cluster labels
    """

    name: str = "exhibitor_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are the Exhibitor Agent for ConfMind. Your job is to cluster "
                    "exhibitors — NOT discover new ones.\n\n"
                    "CRITICAL RULES:\n"
                    "1. Extract exhibitors ONLY from past_events data.\n"
                    "2. Cluster each into one of: startup, enterprise, tools_platform, "
                    "media, individual, government.\n"
                    "3. An exhibitor can belong to EXACTLY ONE cluster.\n"
                    "4. If a cluster is empty, you may do ONE Tavily gap-fill query.\n"
                    "5. Maximum 3 Tavily gap-fill queries total.\n"
                    "6. Relevance score (0-10) based on how well the exhibitor fits "
                    "the event category.\n"
                    "7. NEVER hallucinate exhibitor data.\n"
                    "8. Output valid JSON when asked.",
                ),
                ("human", "{input}"),
            ]
        )

    # ── Pass 1: Extract from past_events ──────────────────────────────────

    def _extract_exhibitors(self, past_events: list[dict]) -> list[dict[str, Any]]:
        """Extract exhibitor names from past_events."""
        exhibitor_counter: Counter = Counter()

        for event in past_events:
            exhibitors = event.get("exhibitors", [])
            if isinstance(exhibitors, list):
                for e in exhibitors:
                    if isinstance(e, str) and e.strip():
                        exhibitor_counter[e.strip()] += 1

        exhibitors = []
        for name, count in exhibitor_counter.most_common():
            exhibitors.append({
                "name": name,
                "frequency": count,
                "cluster": "",
                "relevance": 0.0,
            })

        self._log_info(f"Extracted {len(exhibitors)} unique exhibitors")
        return exhibitors

    # ── Pass 2: LLM clustering ───────────────────────────────────────────

    def _cluster_exhibitors(
        self, exhibitors: list[dict], category: str
    ) -> dict[str, list[dict]]:
        """Use LLM to assign each exhibitor to a cluster."""
        if not exhibitors:
            return {label: [] for label in _CLUSTER_LABELS}

        # Batch cluster for efficiency
        exhibitor_names = [e["name"] for e in exhibitors]
        batch_prompt = (
            f"Classify each of these exhibitors into EXACTLY ONE cluster.\n\n"
            f"Clusters:\n"
            f"- startup: early-stage companies, usually <50 employees\n"
            f"- enterprise: large corporations, established brands\n"
            f"- tools_platform: SaaS tools, dev platforms, infrastructure\n"
            f"- media: publishers, news outlets, content creators\n"
            f"- individual: solo consultants, freelancers, individual brands\n"
            f"- government: government agencies, public sector orgs\n\n"
            f"Event category: {category}\n\n"
            f"Exhibitors:\n{', '.join(exhibitor_names[:50])}\n\n"
            f"Output as JSON object mapping exhibitor name to cluster label.\n"
            f"Example: {{\"CompanyA\": \"startup\", \"CompanyB\": \"enterprise\"}}\n\n"
            f"Output ONLY valid JSON."
        )
        cluster_map = self._invoke_llm_json(batch_prompt)

        # Apply cluster assignments
        clusters: dict[str, list[dict]] = {label: [] for label in _CLUSTER_LABELS}
        for exhibitor in exhibitors:
            name = exhibitor["name"]
            cluster = "individual"  # Default fallback
            if cluster_map and isinstance(cluster_map, dict):
                assigned = cluster_map.get(name, "individual")
                if assigned in _CLUSTER_LABELS:
                    cluster = assigned
            exhibitor["cluster"] = cluster
            clusters[cluster].append(exhibitor)

        # Log cluster distribution
        for label, members in clusters.items():
            self._log_info(f"  Cluster [{label}]: {len(members)} exhibitors")

        return clusters

    # ── Pass 3: Gap-fill empty clusters ──────────────────────────────────

    def _gap_fill_clusters(
        self,
        clusters: dict[str, list[dict]],
        category: str,
        geography: str,
    ) -> dict[str, list[dict]]:
        """Fill empty clusters with Tavily discovery (max 3 queries)."""
        queries_used = 0
        max_queries = 3

        for label in _CLUSTER_LABELS:
            if clusters[label] or queries_used >= max_queries:
                continue

            self._log_info(f"  Gap-filling cluster [{label}]...")
            query = f"{label} companies exhibiting at {category} events {geography} 2025"
            results = self._tavily_search(query, max_results=3)
            queries_used += 1

            if results:
                combined = "\n".join(r.get("content", "") for r in results)
                extract_prompt = (
                    f"From the following text, extract {label} companies that exhibit "
                    f"at {category} events.\n\n"
                    f"Text: {combined[:2000]}\n\n"
                    f"Output ONLY a JSON list of strings."
                )
                names = self._invoke_llm_json(extract_prompt)
                if names and isinstance(names, list):
                    for name in names[:3]:  # Max 3 per cluster
                        if isinstance(name, str) and name.strip():
                            clusters[label].append({
                                "name": name.strip(),
                                "frequency": 0,
                                "cluster": label,
                                "relevance": 3.0,  # Lower score for gap-filled
                            })

        return clusters

    # ── Scoring ──────────────────────────────────────────────────────────

    def _score_exhibitors(
        self, exhibitors: list[dict], category: str
    ) -> list[dict]:
        """Score each exhibitor's relevance to the event category."""
        for exhibitor in exhibitors:
            freq = exhibitor.get("frequency", 0)
            # Simple scoring: frequency-based + cluster bonus
            freq_score = min(5.0, freq * 1.5)
            cluster = exhibitor.get("cluster", "")
            # Cluster bonus based on typical event relevance
            cluster_bonus = {
                "enterprise": 3.0,
                "tools_platform": 2.5,
                "startup": 2.0,
                "media": 1.5,
                "government": 1.0,
                "individual": 0.5,
            }.get(cluster, 1.0)
            exhibitor["relevance"] = round(min(10.0, freq_score + cluster_bonus), 2)

        return exhibitors

    # ── Main run ──────────────────────────────────────────────────────────

    def run(self, state: AgentState) -> dict[str, Any]:
        """Execute the 3-pass exhibitor clustering pipeline."""
        self._current_pass = 0
        self._log_info("Starting exhibitor clustering run...")

        try:
            cfg = state["event_config"]
            category = cfg.category
            geography = cfg.geography
            past_events = state.get("past_events", [])

            # ── Pass 1: Extract from past_events ──────────────────────────
            with self._pass_context(
                "Pass 1: Extract exhibitors", state,
                f"exhibitors for {category} events"
            ):
                exhibitors = self._extract_exhibitors(past_events)

            # ── Pass 2: LLM clustering ────────────────────────────────────
            with self._pass_context(
                "Pass 2: LLM clustering", state,
                f"clustering exhibitors for {category}"
            ):
                clusters = self._cluster_exhibitors(exhibitors, category)

            # ── Pass 3: Gap-fill empty clusters ──────────────────────────
            with self._pass_context(
                "Pass 3: Gap-fill empty clusters", state,
                f"gap-filling exhibitor clusters for {category}"
            ):
                clusters = self._gap_fill_clusters(clusters, category, geography)

            # ── Flatten clusters + score ──────────────────────────────────
            all_exhibitors = []
            for label, members in clusters.items():
                all_exhibitors.extend(members)

            all_exhibitors = self._score_exhibitors(all_exhibitors, category)
            all_exhibitors.sort(key=lambda e: e.get("relevance", 0), reverse=True)

            # ── Build output ExhibitorSchema list ─────────────────────────
            exhibitor_schemas = []
            for e in all_exhibitors:
                exhibitor_schemas.append(ExhibitorSchema(
                    name=e["name"],
                    cluster=e.get("cluster", "individual"),
                    relevance=min(10.0, e.get("relevance", 0)),
                    website="",
                ))

            # Write to memory
            docs = [f"Exhibitor: {e.name} | Cluster: {e.cluster}" for e in exhibitor_schemas]
            meta = [{"name": e.name, "cluster": e.cluster} for e in exhibitor_schemas]
            self._write_memory(docs, meta, collection="events")

            self._log_info(f"Completed — {len(exhibitor_schemas)} exhibitors in {sum(1 for c in clusters.values() if c)}/{len(_CLUSTER_LABELS)} clusters")

            return {"exhibitors": exhibitor_schemas}

        except Exception as exc:
            return self._log_error(state, f"ExhibitorAgent failed: {exc}")
