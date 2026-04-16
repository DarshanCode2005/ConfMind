
import asyncio
import os
import sys

# Add current directory to path so it finds 'backend'
sys.path.insert(0, os.path.abspath("."))

from backend.agents.sponsor_agent import SponsorAgent
from backend.models.schemas import AgentState, EventConfigInput

async def test_agent():
    print("Initializing SponsorAgent...")
    agent = SponsorAgent()
    
    state: AgentState = {
        "event_config": EventConfigInput(
            category="AI",
            geography="San Francisco",
            audience_size=500,
            budget_usd=100000,
            event_dates="2025-10-01",
            event_name="AI Future Summit"
        ),
        "sponsors": [],
        "metadata": {"plan_id": "test-root"}
    }
    
    print("Running SponsorAgent...")
    # Mocking the actual LLM call to avoid costs/delays if possible, 
    # but the user wants to see it working "seamlessly".
    # Let's try running it for real but with a tiny scope or mock search.
    
    try:
        # If we have keys, let's try a real run
        if os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"):
             result = await agent.run(state)
             print(f"Success! Found {len(result.get('sponsors', []))} sponsors.")
        else:
             print("Skipping real run - no API keys found in .env")
             
    except Exception as e:
        print(f"Agent failed: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(test_agent())
