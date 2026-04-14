"""
event_ops_agent.py — Operations and scheduling agent for ConfMind.

Generates a greedy draft schedule by assigning speakers to available time slots
and rooms (if venue data available).
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_TIME_SLOTS = [
    "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM (Lunch)", 
    "01:30 PM", "02:30 PM", "03:30 PM", "04:30 PM (Closing)"
]

class EventOpsAgent(BaseAgent):
    """Generates a preliminary event schedule."""

    name: str = "event_ops_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        """Ops agent uses deterministic logic, but we still define the prompt contract."""
        return ChatPromptTemplate.from_messages(
            [
                ("system", "You are an event operations manager. You coordinate logistics and scheduling."),
                ("human", "{input}"),
            ]
        )

    def run(self, state: AgentState) -> AgentState:
        try:
            speakers = state.get("speakers", [])
            venues = state.get("venues", [])
            
            # Use the first venue's name if available, else "Main Hall"
            room_name = venues[0].name if venues else "Main Hall"
            
            schedule = []
            speaker_idx = 0
            
            for slot in _TIME_SLOTS:
                entry = {
                    "time": slot,
                    "room": room_name,
                    "speaker": "TBA",
                    "topic": "Networking / Break"
                }
                
                # Assign a speaker if it's not a break/lunch and we have speakers left
                if "Lunch" not in slot and "Closing" not in slot and speaker_idx < len(speakers):
                    s = speakers[speaker_idx]
                    entry["speaker"] = s.name
                    entry["topic"] = s.topic or "Keynote Presentation"
                    speaker_idx += 1
                
                schedule.append(entry)

            # ── 3. Write results ──────────────────────────────────────────────
            return {"schedule": schedule}

        except Exception as exc:
            return self._log_error({}, f"EventOpsAgent failed: {exc}")
