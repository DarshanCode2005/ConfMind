import sys
from unittest.mock import MagicMock, patch

def test_imports():
    print("Testing imports...")
    mock_llm_class = MagicMock()
    
    modules_to_mock = [
        'backend.tools.serper_tool',
        'backend.tools.scraper_tool',
        'backend.tools.linkedin_tool',
        'backend.tools.pdf_generator',
        'backend.memory.vector_store',
        'langchain_openai',
        'scrapegraphai.graphs',
        'chromadb',
        'pinecone',
        'sklearn.linear_model',
        'sklearn.preprocessing'
    ]
    
    with patch.dict('sys.modules', {m: MagicMock() for m in modules_to_mock}):
        try:
            from backend.agents.sponsor_agent import SponsorAgent
            print("Imported SponsorAgent")
            from backend.agents.speaker_agent import SpeakerAgent
            print("Imported SpeakerAgent")
            from backend.agents.exhibitor_agent import ExhibitorAgent
            print("Imported ExhibitorAgent")
            from backend.agents.venue_agent import VenueAgent
            print("Imported VenueAgent")
            from backend.agents.pricing_agent import PricingAgent
            print("Imported PricingAgent")
            from backend.agents.revenue_agent import RevenueAgent
            print("Imported RevenueAgent")
            from backend.agents.community_gtm_agent import CommunityGTMAgent
            print("Imported CommunityGTMAgent")
            from backend.agents.event_ops_agent import EventOpsAgent
            print("Imported EventOpsAgent")
            
            from backend.orchestrator import run_plan, graph
            print("Imported Orchestrator")
            
            print(f"Graph nodes: {list(graph.nodes.keys())}")
            expected_nodes = {
                "sponsor_agent", "speaker_agent", "exhibitor_agent", "venue_agent",
                "pricing_agent", "revenue_agent", "community_gtm_agent", "event_ops_agent"
            }
            found_nodes = set(graph.nodes.keys())
            missing = expected_nodes - found_nodes
            if missing:
                print(f"MISSING NODES: {missing}")
            else:
                print("All 8 agent nodes are present in the graph.")

        except Exception as e:
            print(f"Import failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_imports()
