import os
import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the root directory to sys.path
root_dir = Path(__file__).parent.parent.resolve()
sys.path.append(str(root_dir))
sys.path.append(str(root_dir / "backend"))

# Mock heavy/problematic libraries before importing orchestrator
sys.modules["pandas"] = MagicMock()
sys.modules["sklearn"] = MagicMock()
sys.modules["sklearn.linear_model"] = MagicMock()
sys.modules["sklearn.preprocessing"] = MagicMock()

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration

# --- MOCK LLM FOR INSTANT ORCHESTRATION TESTING ---
class MockLLM(BaseChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # Return a simple JSON string that satisfy most agents' parsing needs
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content='[]'))])
    
    def _llm_type(self) -> str:
        return "mock-chat-ollama"

# Patch BaseAgent._get_llm to skip real Ollama calls during this test
patcher_llm = patch('backend.agents.base_agent.BaseAgent._get_llm', return_value=MockLLM())
patcher_llm.start()

from backend.orchestrator import run_plan
from backend.models.schemas import EventConfigInput

# --- MOCKING TOOLS FOR STABLE TESTING ---
mock_serper = MagicMock()
mock_scraper = MagicMock()
mock_linkedin = MagicMock()

# Patching the tool modules to bypass real API/Heavy scraping during this test
patcher1 = patch('backend.tools.serper_tool.search_sponsors', mock_serper.search_sponsors)
patcher2 = patch('backend.tools.serper_tool.search_communities', mock_serper.search_communities)
patcher5 = patch('backend.tools.serper_tool.search_venues', mock_serper.search_venues)
patcher6 = patch('backend.tools.serper_tool.search_speakers', mock_serper.search_speakers)
patcher3 = patch('backend.tools.scraper_tool.search_sponsors_structured', mock_scraper.search_sponsors_structured)
patcher4 = patch('backend.tools.linkedin_tool.enrich_speakers', mock_linkedin.enrich_speakers)

# Also patch them where they are imported to be safe
patcher_sa = patch('backend.agents.sponsor_agent.search_sponsors_structured', mock_scraper.search_sponsors_structured)
patcher_va = patch('backend.agents.venue_agent.search_venues', mock_serper.search_venues)
patcher_spa = patch('backend.agents.speaker_agent.search_speakers', mock_serper.search_speakers)
patcher_spa2 = patch('backend.agents.speaker_agent.enrich_speakers', mock_linkedin.enrich_speakers)

patcher1.start()
patcher2.start()
patcher3.start()
patcher4.start()
patcher5.start()
patcher6.start()
patcher_sa.start()
patcher_va.start()
patcher_spa.start()
patcher_spa2.start()

# Setup mock returns
mock_serper.search_sponsors.return_value = []
mock_serper.search_communities.return_value = []
mock_serper.search_venues.return_value = []
mock_serper.search_speakers.return_value = []
mock_scraper.search_sponsors_structured.return_value = []
mock_linkedin.enrich_speakers.return_value = []

async def monitor_agents():
    print("="*60)
    print("      CONFMIND AGENT MONITORING SESSION")
    print("="*60)

    # 1. Configuration
    config = EventConfigInput(
        category="AI & Machine Learning",
        geography="London",
        audience_size=1200,
        budget_usd=75000.0,
        event_dates="2025-11-20",
        event_name="Global AI Summit 2025"
    )

    print(f"\n[ORCHESTRATOR] Starting plan for: {config.event_name}")
    print(f"[ORCHESTRATOR] Target: {config.category} in {config.geography}")
    print("-" * 60)

    try:
        # 2. Run the plan
        final_state = await run_plan(config)

        # 3. Final Summary Output
        print("\n" + "="*60)
        print("             FINAL PLAN SUMMARY")
        print("="*60)
        
        print(f"\n[SPONSORS] Found {len(final_state['sponsors'])} candidates.")
        print(f"[SPEAKERS] Captured {len(final_state['speakers'])} influencers.")
        print(f"[VENUES] Identified {len(final_state['venues'])} options.")

        print(f"\n[FINANCIALS]")
        rev = final_state['revenue']
        print(f"  - Total Projected Revenue: ${rev.get('total_projected_revenue', 0):,.2f}")
        print(f"  - Budget: ${rev.get('budget_usd', 0):,.2f}")

        if final_state['errors']:
            print("\n" + "!"*60)
            print("                ERRORS ENCOUNTERED")
            print("!"*60)
            for err in final_state['errors']:
                print(f"  [!] {err}")

    except Exception as e:
        print(f"\n[FATAL ERROR] Orchestration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("[SYSTEM] Starting test in MOCK mode for instant verification...")
    asyncio.run(monitor_agents())
