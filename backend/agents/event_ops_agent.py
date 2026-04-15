"""
event_ops_agent.py — Event Operations & Scheduling Agent for ConfMind.

System Prompt:
  "You are the Event Ops Agent. Build conflict-free schedule only."

No external tools. Use agenda_draft + venues. Assume duration from target_size.
Generate slots → detect conflicts → resolve up to 3 times.
"""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_MAX_CONFLICT_RESOLUTIONS = 3

# Duration assumptions based on audience size
_DURATION_MAP = {
    (0, 200): {"days": 1, "sessions_per_day": 4, "session_minutes": 45},
    (200, 500): {"days": 1, "sessions_per_day": 6, "session_minutes": 45},
    (500, 1000): {"days": 2, "sessions_per_day": 6, "session_minutes": 45},
    (1000, 5000): {"days": 3, "sessions_per_day": 8, "session_minutes": 40},
    (5000, float("inf")): {"days": 3, "sessions_per_day": 10, "session_minutes": 30},
}

# Standard time slots for a conference day
_BASE_SLOTS = [
    ("09:00", "09:45", "Opening Keynote"),
    ("10:00", "10:45", "Session"),
    ("11:00", "11:45", "Session"),
    ("12:00", "13:00", "Lunch Break"),
    ("13:00", "13:45", "Session"),
    ("14:00", "14:45", "Session"),
    ("15:00", "15:15", "Networking Break"),
    ("15:15", "16:00", "Session"),
    ("16:15", "17:00", "Session"),
    ("17:00", "17:45", "Closing / Panel"),
]


class EventOpsAgent(BaseAgent):
    """Builds a conflict-free event schedule using agenda + venues.

    NO external tools. Uses only data already in state:
        - speakers + agenda_draft (from SpeakerAgent)
        - venues (from VenueAgent)
        - event_config for sizing

    Output:
        state["schedule"] — list of schedule entry dicts
    """

    name: str = "event_ops_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are the Event Ops Agent for ConfMind. You build conflict-free "
                    "event schedules.\n\n"
                    "CRITICAL RULES:\n"
                    "1. NO external tools — work only with data in state.\n"
                    "2. No speaker can be in two sessions at the same time.\n"
                    "3. No room can host two sessions at the same time.\n"
                    "4. Include breaks: lunch (60min), networking (15min).\n"
                    "5. Duration scales with target_size:\n"
                    "   - <200: 1 day, 4 sessions\n"
                    "   - 200-500: 1 day, 6 sessions\n"
                    "   - 500-1000: 2 days, 6 sessions/day\n"
                    "   - 1000-5000: 3 days, 8 sessions/day\n"
                    "   - 5000+: 3 days, 10 sessions/day\n"
                    "6. Resolve conflicts up to 3 times, then accept.\n"
                    "7. High-influence speakers get keynote/prime slots.\n"
                    "8. Output as structured JSON schedule.",
                ),
                ("human", "{input}"),
            ]
        )

    # ── Determine event duration ──────────────────────────────────────────

    def _get_duration_params(self, target_size: int) -> dict[str, Any]:
        """Determine event duration and sessions based on target_size."""
        for (low, high), params in _DURATION_MAP.items():
            if low <= target_size < high:
                return params
        return _DURATION_MAP[(1000, 5000)]  # Default

    # ── Generate slots ────────────────────────────────────────────────────

    def _generate_slots(
        self,
        num_days: int,
        sessions_per_day: int,
        session_minutes: int,
        venues: list,
        speakers: list,
        agenda_draft: list[dict],
    ) -> list[dict[str, Any]]:
        """Generate initial schedule slots."""
        schedule = []

        # Get room names from venues
        rooms = []
        if venues:
            for v in venues[:3]:  # Max 3 parallel tracks
                rooms.append(getattr(v, "name", None) or v.get("name", "Main Hall"))
        if not rooms:
            rooms = ["Main Hall"]

        # Get speaker list
        speaker_list = []
        for s in speakers:
            name = getattr(s, "name", None) or s.get("name", "")
            score = getattr(s, "influence_score", None) or s.get("influence_score", 0)
            topic = getattr(s, "topic", None) or s.get("topic", "")
            if name:
                speaker_list.append({"name": name, "score": score, "topic": topic})

        # Sort speakers by influence for slot assignment priority
        speaker_list.sort(key=lambda s: s.get("score", 0), reverse=True)

        # Get agenda topics
        topics = []
        if agenda_draft:
            for item in agenda_draft:
                if isinstance(item, dict):
                    topics.append({
                        "topic": item.get("topic", "Session"),
                        "format": item.get("format", "session"),
                        "speakers": item.get("speakers", []),
                    })

        speaker_idx = 0
        topic_idx = 0

        for day in range(1, num_days + 1):
            session_count = 0

            for start_time, end_time, slot_type in _BASE_SLOTS:
                if session_count >= sessions_per_day and "Break" not in slot_type and "Lunch" not in slot_type:
                    continue

                # Break/lunch slots
                if "Break" in slot_type or "Lunch" in slot_type:
                    schedule.append({
                        "day": day,
                        "time_start": start_time,
                        "time_end": end_time,
                        "room": "All",
                        "speaker": "—",
                        "topic": slot_type,
                        "format": "break",
                    })
                    continue

                # Session slots — assign across rooms
                for room in rooms:
                    if session_count >= sessions_per_day:
                        break

                    # Determine speaker
                    speaker_name = "TBA"
                    speaker_topic = "Open Session"

                    # Try to use agenda draft first
                    if topic_idx < len(topics):
                        topic_info = topics[topic_idx]
                        speaker_topic = topic_info.get("topic", "Session")
                        assigned_speakers = topic_info.get("speakers", [])
                        if assigned_speakers:
                            speaker_name = assigned_speakers[0]
                        elif speaker_idx < len(speaker_list):
                            speaker_name = speaker_list[speaker_idx]["name"]
                            speaker_idx += 1
                        topic_idx += 1
                    elif speaker_idx < len(speaker_list):
                        sp = speaker_list[speaker_idx]
                        speaker_name = sp["name"]
                        speaker_topic = sp.get("topic", "Keynote Presentation")
                        speaker_idx += 1

                    # Determine format
                    entry_format = "session"
                    if "Keynote" in slot_type or (speaker_idx <= 2 and day == 1):
                        entry_format = "keynote"
                    elif "Panel" in slot_type:
                        entry_format = "panel"

                    schedule.append({
                        "day": day,
                        "time_start": start_time,
                        "time_end": end_time,
                        "room": room,
                        "speaker": speaker_name,
                        "topic": speaker_topic,
                        "format": entry_format,
                    })
                    session_count += 1

        self._log_info(f"Generated {len(schedule)} schedule entries across {num_days} day(s)")
        return schedule

    # ── Conflict detection ────────────────────────────────────────────────

    def _detect_conflicts(self, schedule: list[dict]) -> list[dict[str, Any]]:
        """Detect scheduling conflicts (speaker or room double-booking)."""
        conflicts = []

        # Group by (day, time_start) to find parallel sessions
        time_groups: dict[tuple, list[dict]] = {}
        for entry in schedule:
            if entry.get("format") == "break":
                continue
            key = (entry["day"], entry["time_start"])
            if key not in time_groups:
                time_groups[key] = []
            time_groups[key].append(entry)

        for key, entries in time_groups.items():
            # Speaker conflict: same speaker in multiple rooms
            speakers = [e["speaker"] for e in entries if e["speaker"] not in ("TBA", "—")]
            speaker_set = set()
            for s in speakers:
                if s in speaker_set:
                    conflicts.append({
                        "type": "speaker_double_booking",
                        "day": key[0],
                        "time": key[1],
                        "speaker": s,
                    })
                speaker_set.add(s)

            # Room conflict: same room used twice
            rooms = [e["room"] for e in entries if e["room"] != "All"]
            room_set = set()
            for r in rooms:
                if r in room_set:
                    conflicts.append({
                        "type": "room_double_booking",
                        "day": key[0],
                        "time": key[1],
                        "room": r,
                    })
                room_set.add(r)

        return conflicts

    # ── Conflict resolution ──────────────────────────────────────────────

    def _resolve_conflicts(self, schedule: list[dict], conflicts: list[dict]) -> list[dict]:
        """Resolve conflicts by swapping or rescheduling."""
        if not conflicts:
            return schedule

        for conflict in conflicts:
            if conflict["type"] == "speaker_double_booking":
                # Find all entries for this speaker at this time
                speaker = conflict["speaker"]
                day = conflict["day"]
                time = conflict["time"]

                matching = [
                    (i, e) for i, e in enumerate(schedule)
                    if e["speaker"] == speaker
                    and e["day"] == day
                    and e["time_start"] == time
                ]

                # Keep the first, move the rest to next available slot
                for idx, entry in matching[1:]:
                    # Find next available slot
                    for j, other in enumerate(schedule):
                        if (
                            other["speaker"] == "TBA"
                            and other.get("format") != "break"
                        ):
                            schedule[j]["speaker"] = entry["speaker"]
                            schedule[j]["topic"] = entry["topic"]
                            schedule[idx]["speaker"] = "TBA"
                            schedule[idx]["topic"] = "Open Session"
                            break

        return schedule

    # ── Main run ──────────────────────────────────────────────────────────

    def run(self, state: AgentState) -> dict[str, Any]:
        """Build a conflict-free schedule. No external tools."""
        self._current_pass = 0
        self._log_info("Starting schedule generation...")

        try:
            cfg = state["event_config"]
            target_size = cfg.audience_size
            speakers = state.get("speakers", [])
            venues = state.get("venues", [])
            agenda_draft = state.get("metadata", {}).get("agenda_draft", [])

            # ── Determine duration ────────────────────────────────────────
            with self._pass_context(
                "Determine event parameters", state,
                f"schedule for {target_size} attendees"
            ):
                params = self._get_duration_params(target_size)
                self._log_info(
                    f"Event params: {params['days']} day(s), "
                    f"{params['sessions_per_day']} sessions/day, "
                    f"{params['session_minutes']}min each"
                )

            # ── Generate initial schedule ─────────────────────────────────
            with self._pass_context(
                "Generate initial schedule", state,
                f"scheduling {len(speakers)} speakers across {len(venues)} venues"
            ):
                schedule = self._generate_slots(
                    num_days=params["days"],
                    sessions_per_day=params["sessions_per_day"],
                    session_minutes=params["session_minutes"],
                    venues=venues,
                    speakers=speakers,
                    agenda_draft=agenda_draft if isinstance(agenda_draft, list) else [],
                )

            # ── Conflict detection + resolution (up to 3 rounds) ─────────
            for round_num in range(1, _MAX_CONFLICT_RESOLUTIONS + 1):
                conflicts = self._detect_conflicts(schedule)
                if not conflicts:
                    self._log_info(f"No conflicts detected after round {round_num}")
                    break
                self._log_info(f"Round {round_num}: {len(conflicts)} conflicts detected — resolving")
                schedule = self._resolve_conflicts(schedule, conflicts)

            # Final conflict check
            remaining = self._detect_conflicts(schedule)
            if remaining:
                self._log_info(f"Warning: {len(remaining)} unresolved conflicts remain")

            # Write to memory
            docs = [f"Schedule: {len(schedule)} entries across {params['days']} days"]
            meta = [{"total_entries": len(schedule), "days": params['days']}]
            self._write_memory(docs, meta, collection="events")

            self._log_info(f"Completed — {len(schedule)} schedule entries")

            return {"schedule": schedule}

        except Exception as exc:
            return self._log_error(state, f"EventOpsAgent failed: {exc}")
