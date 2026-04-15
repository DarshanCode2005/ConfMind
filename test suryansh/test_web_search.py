import os
import sys
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).parent.parent.resolve()
sys.path.append(str(root_dir))
sys.path.append(str(root_dir / "backend"))

load_dotenv(root_dir / ".env")

from backend.agents.web_search_agent import WebSearchAgent
from backend.models.schemas import EventConfigInput

def test_web_search():
    print("="*60)
    print("Testing WebSearchAgent (PredictHQ + Tavily Enrich)")
    print("="*60)
    
    agent = WebSearchAgent(agent_id=1, limit=5, category="conferences", geography="San Francisco, CA")
    
    # Mocking AgentState slightly
    config = EventConfigInput(
        category="Tech Conferences",
        geography="San Francisco, CA",
        audience_size=500,
        budget_usd=100000.0,
        event_dates="2025-10-10",
        event_name="Future AI Tech Summit"
    )
    
    state = {
        "event_config": config,
        "past_events": [],
    }

    try:
        delta = agent.run(state)
        print("\n--- RESULTS ---")
        past_events = delta.get("past_events", [])
        print(f"Found {len(past_events)} events.")
        print(json.dumps(past_events[:2], indent=2))
        
        errors = delta.get("errors", [])
        if errors:
            print("\nErrors:", errors)
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    test_web_search()
