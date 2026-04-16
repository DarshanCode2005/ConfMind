"""
speaker_agent.py — Speaker/Artist discovery, scoring, and agenda mapping agent.

System Prompt:
  "You are the Speaker/Artist Agent. Discover, score, and map to agenda.
   Prioritize past speakers then expand."

Loop (5 passes):
  • Pass 1: Extract from past_events.
  • Pass 2: Tavily "{speaker_name} speaker {category} LinkedIn followers
            publications 2025".
  • Pass 3: Score influence.
  • Pass 4: If <10 speakers → one expansion Tavily "top {category} speakers
            {geography} 2025 2026".
  • Pass 5: LLM agenda mapping (6–10 topics).

Stop: ≥15 speakers OR 2 expansions.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState, SpeakerSchema

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_MIN_SPEAKERS = 10
_TARGET_SPEAKERS = 15
_MAX_EXPANSIONS = 2
_AGENDA_TOPICS = (6, 10)  # min, max topics for agenda mapping


class SpeakerAgent(BaseAgent):
    """Discovers, scores, and maps speakers to an event agenda.

    Sources:
        1. past_events from WebSearchAgent
        2. Tavily enrichment for influence scoring
        3. LLM for influence scoring + agenda topic mapping

    Output:
        state["speakers"]   — list of SpeakerSchema, scored and ranked
        state["metadata"]   — agenda_draft key with topic-to-speaker mapping
    """

    name: str = "speaker_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are the Speaker/Artist Agent for ConfMind. You discover, "
                    "score, and map speakers to an event agenda.\n\n"
                    "CRITICAL RULES:\n"
                    "1. Prioritize speakers from past_events data first — they are proven.\n"
                    "2. Expand to new speakers ONLY if you have fewer than 10.\n"
                    "3. Score influence based on: LinkedIn followers, publications, "
                    "speaking experience, topic relevance, and geographic fit.\n"
                    "4. Agenda mapping: assign speakers to 6-10 topics relevant to the "
                    "event category.\n"
                    "5. For music festivals, 'speakers' = 'artists/performers'.\n"
                    "6. For sports events, 'speakers' = 'commentators/athletes/coaches'.\n"
                    "7. NEVER hallucinate speaker credentials. Missing data = null.\n"
                    "8. Output valid JSON when asked.",
                ),
                ("human", "{input}"),
            ]
        )

    # ── Pass 1: Extract from past_events ──────────────────────────────────

    def _extract_speakers(self, past_events: list[dict]) -> list[dict[str, Any]]:
        """Extract speaker names from past_events, track frequency."""
        speaker_counter: Counter = Counter()
        speaker_topics: dict[str, set] = {}

        for event in past_events:
            speakers = event.get("speakers", [])
            category = event.get("category", "")
            if isinstance(speakers, list):
                for s in speakers:
                    if isinstance(s, str) and s.strip():
                        name = s.strip()
                        speaker_counter[name] += 1
                        if name not in speaker_topics:
                            speaker_topics[name] = set()
                        if category:
                            speaker_topics[name].add(category)

        speakers = []
        for name, count in speaker_counter.most_common():
            speakers.append({
                "name": name,
                "frequency": count,
                "topics": list(speaker_topics.get(name, [])),
                "enrichment": {},
                "influence_score": 0.0,
            })

        self._log_info(f"Extracted {len(speakers)} unique speakers from past events")
        return speakers

    # ── Pass 2: Tavily enrichment ─────────────────────────────────────────

    def _enrich_speakers(self, speakers: list[dict], category: str) -> list[dict]:
        """Enrich speakers with LinkedIn/publications data via Tavily."""
        for speaker in speakers[:20]:  # Enrich top 20
            name = speaker["name"]
            query = f"{name} speaker {category} LinkedIn followers publications 2025"
            results = self._tavily_search(query, max_results=3)

            if results:
                combined = "\n".join(r.get("content", "") for r in results)
                speaker["enrichment"] = {
                    "raw_content": combined[:2000],
                    "source_urls": [r.get("url", "") for r in results],
                }
                self._log_info(f"  Enriched: {name}")

        return speakers

    # ── Pass 3: Score influence ───────────────────────────────────────────

    def _score_speakers(self, speakers: list[dict], category: str, geography: str) -> list[dict]:
        """Score each speaker's influence via LLM analysis."""
        for speaker in speakers:
            enrichment_text = speaker.get("enrichment", {}).get("raw_content", "")
            topics = ", ".join(speaker.get("topics", []))

            score_prompt = (
                f"Rate the influence of '{speaker['name']}' as a speaker for a "
                f"'{category}' event in {geography} on a scale of 0-10.\n\n"
                f"Consider:\n"
                f"- Speaking frequency: appeared in {speaker.get('frequency', 1)} past events\n"
                f"- Known topics: {topics}\n"
                f"- Additional context: {enrichment_text[:500]}\n\n"
                f"Factors to weigh:\n"
                f"1. LinkedIn followers / social media presence (30%)\n"
                f"2. Publications / speaking credentials (25%)\n"
                f"3. Topic relevance to {category} (25%)\n"
                f"4. Geographic fit for {geography} (20%)\n\n"
                f"Output ONLY a single number between 0 and 10."
            )
            raw_score = self._invoke_llm(score_prompt, temperature=0.1)
            try:
                speaker["influence_score"] = min(10.0, max(0.0, float(raw_score)))
            except (ValueError, TypeError):
                speaker["influence_score"] = 3.0  # Default mid-low

        return speakers

    # ── Pass 4: Expansion ─────────────────────────────────────────────────

    def _expand_speakers(
        self, speakers: list[dict], category: str, geography: str, expansion_round: int
    ) -> list[dict]:
        """If <10 speakers, discover new ones via Tavily."""
        if len(speakers) >= _MIN_SPEAKERS:
            return speakers

        self._log_info(f"Only {len(speakers)} speakers — expanding (round {expansion_round})")
        query = f"top {category} speakers {geography} 2025 2026 keynote"
        results = self._tavily_search(query, max_results=5)

        if results:
            combined = "\n".join(r.get("content", "") for r in results)
            extract_prompt = (
                f"From the following text, extract a list of speaker/presenter names "
                f"relevant to {category} events.\n\n"
                f"Text: {combined[:3000]}\n\n"
                f"Output ONLY a JSON list of strings. Example: [\"Name 1\", \"Name 2\"]"
            )
            names = self._invoke_llm_json(extract_prompt)
            if names and isinstance(names, list):
                existing_names = {s["name"].lower() for s in speakers}
                for name in names:
                    if isinstance(name, str) and name.strip().lower() not in existing_names:
                        speakers.append({
                            "name": name.strip(),
                            "frequency": 0,
                            "topics": [category],
                            "enrichment": {},
                            "influence_score": 2.0,  # Default for discovered speakers
                        })
                        existing_names.add(name.strip().lower())

        self._log_info(f"After expansion: {len(speakers)} speakers")
        return speakers

    # ── Pass 5: Agenda mapping ────────────────────────────────────────────

    def _map_agenda(self, speakers: list[dict], category: str) -> list[dict[str, Any]]:
        """Use LLM to map speakers to 6-10 agenda topics."""
        speaker_list = "\n".join(
            f"- {s['name']} (score: {s.get('influence_score', 0)}, "
            f"topics: {', '.join(s.get('topics', []))})"
            for s in speakers[:_TARGET_SPEAKERS]
        )

        agenda_prompt = (
            f"Create an agenda for a {category} event with 6-10 session topics.\n\n"
            f"Available speakers:\n{speaker_list}\n\n"
            f"For each topic, assign the most suitable speaker(s).\n\n"
            f"Output as JSON array:\n"
            f"[{{\"topic\": \"Topic Name\", \"speakers\": [\"Name 1\"], "
            f"\"format\": \"keynote|panel|workshop\"}}]\n\n"
            f"Output ONLY valid JSON."
        )
        agenda = self._invoke_llm_json(agenda_prompt)
        if agenda and isinstance(agenda, list):
            return agenda
        return []

    # ── Main run ──────────────────────────────────────────────────────────

    def run(self, state: AgentState) -> dict[str, Any]:
        """Execute the 5-pass speaker discovery pipeline."""
        self._current_pass = 0
        self._log_info("Starting speaker discovery run...")

        try:
            cfg = state["event_config"]
            category = cfg.category
            geography = cfg.geography
            past_events = state.get("past_events", [])

            # ── Pass 1: Extract from past_events ──────────────────────────
            with self._pass_context(
                "Pass 1: Extract speakers", state,
                f"speakers for {category} events"
            ):
                speakers = self._extract_speakers(past_events)

            # Fallback if no speakers from past_events
            if not speakers:
                self._log_info("No speakers from past_events — searching directly")
                results = self._tavily_search(
                    f"{category} keynote speakers {geography} 2025", max_results=5
                )
                for r in results:
                    extract_prompt = (
                        f"Extract speaker names from: {r.get('content', '')[:2000]}\n\n"
                        f"Output ONLY a JSON list of strings."
                    )
                    names = self._invoke_llm_json(extract_prompt)
                    if names and isinstance(names, list):
                        for name in names:
                            if isinstance(name, str) and name.strip():
                                speakers.append({
                                    "name": name.strip(),
                                    "frequency": 1,
                                    "topics": [category],
                                    "enrichment": {},
                                    "influence_score": 0.0,
                                })

            # ── Pass 2: Tavily enrichment ─────────────────────────────────
            with self._pass_context(
                "Pass 2: Tavily enrichment", state,
                f"enriching speakers for {category}"
            ):
                speakers = self._enrich_speakers(speakers, category)

            # ── Pass 3: Score influence ───────────────────────────────────
            with self._pass_context(
                "Pass 3: Score influence", state,
                f"scoring speakers for {category} in {geography}"
            ):
                speakers = self._score_speakers(speakers, category, geography)

            # ── Pass 4: Expansion (if needed, up to 2 rounds) ────────────
            expansion_count = 0
            while len(speakers) < _MIN_SPEAKERS and expansion_count < _MAX_EXPANSIONS:
                with self._pass_context(
                    f"Pass 4: Expansion round {expansion_count + 1}", state,
                    f"expanding speakers for {category}"
                ):
                    speakers = self._expand_speakers(speakers, category, geography, expansion_count + 1)
                    expansion_count += 1

            # Sort by influence score
            speakers.sort(key=lambda s: s.get("influence_score", 0), reverse=True)

            # ── Pass 5: Agenda mapping ────────────────────────────────────
            with self._pass_context(
                "Pass 5: Agenda mapping", state,
                f"agenda for {category} event"
            ):
                agenda_draft = self._map_agenda(speakers, category)

            # ── Build output SpeakerSchema list ───────────────────────────
            speaker_schemas = []
            for s in speakers[:_TARGET_SPEAKERS]:
                speaker_schemas.append(SpeakerSchema(
                    name=s["name"],
                    bio="",
                    linkedin_url="",
                    topic=", ".join(s.get("topics", [])),
                    region=geography,
                    influence_score=min(10.0, s.get("influence_score", 0)),
                    speaking_experience=s.get("frequency", 0),
                ))

            # Write to memory
            docs = [f"Speaker: {s.name} | Score: {s.influence_score} | Topic: {s.topic}" for s in speaker_schemas]
            meta = [{"name": s.name, "score": s.influence_score} for s in speaker_schemas]
            self._write_memory(docs, meta, collection="speakers")

            # Chat Agent Indexing Contract
            run_id = state.get("metadata", {}).get("run_id", "unknown")
            chat_docs = []
            chat_meta = []
            for s in speakers[:_TARGET_SPEAKERS]:
                name = s["name"]
                topics = ", ".join(s.get("topics", []))
                score = min(10.0, s.get("influence_score", 0))
                freq = s.get("frequency", 0)
                # Find mapped agenda topics for this speaker
                mapped = [a.get("topic", "") for a in agenda_draft if name in a.get("speakers", [])]
                agenda_topics = ", ".join(mapped) if mapped else "none"
                text = (
                    f"{name}. Topics: {topics}. Score: {score}. "
                    f"Past events: {freq}. Agenda: {agenda_topics}"
                )
                chat_docs.append(text)
                chat_meta.append({
                    "agent": "speaker",
                    "run_id": run_id,
                })
            self.index_to_chroma(chat_docs, "chat_index", chat_meta)

            self._log_info(f"Completed — {len(speaker_schemas)} speakers ranked")

            return {
                "speakers": speaker_schemas,
                "metadata": {"agenda_draft": agenda_draft},
            }

        except Exception as exc:
            return self._log_error(state, f"SpeakerAgent failed: {exc}")
