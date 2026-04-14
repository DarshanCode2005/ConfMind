import asyncio
import os
from unittest.mock import MagicMock, patch

# Mock modules that require API keys or complex dependencies
mock_serper = MagicMock()
mock_scraper = MagicMock()
mock_linkedin = MagicMock()
mock_linkedin = MagicMock()
mock_chroma = MagicMock()
mock_pdf = MagicMock()
mock_llm_class = MagicMock()

# Patch the tools before importing orchestrator
with patch.dict('sys.modules', {
    'backend.tools.serper_tool': mock_serper,
    'backend.tools.scraper_tool': mock_scraper,
    'backend.tools.linkedin_tool': mock_linkedin,
    'backend.tools.pdf_generator': mock_pdf,
    'backend.memory.vector_store': mock_chroma,
    'langchain_openai': MagicMock(ChatOpenAI=mock_llm_class),
    'scrapegraphai.graphs': MagicMock(),
    'chromadb': MagicMock(),
    'pinecone': MagicMock(),
}):
    from backend.orchestrator import run_plan, graph
    from backend.models.schemas import EventConfigInput, AgentState, SponsorSchema, SpeakerSchema, VenueSchema, ExhibitorSchema, TicketTierSchema, CommunitySchema

async def main():
    print("Testing Agent Orchestration...")
    
    # ── 1. Setup Mock Returns ────────────────────────────────────────────────
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Mocked LLM Response")
    mock_llm_class.return_value = mock_llm
    mock_llm.bind_tools.return_value = mock_llm
    mock_scraper.search_sponsors_structured.return_value = [
        SponsorSchema(name="Mock Sponsor 1", tier="Gold", relevance_score=9.0)
    ]
    mock_serper.search_sponsors.return_value = []
    
    mock_scraper.search_speakers_structured.return_value = [
        SpeakerSchema(name="Mock Speaker 1", influence_score=8.5)
    ]
    mock_serper.search_speakers.return_value = []
    mock_linkedin.enrich_speakers.side_effect = lambda x: x
    
    mock_serper.search_venues.return_value = []
    mock_scraper.scrape_venue_page.side_effect = Exception("Scrape fail")
    
    mock_scraper.search_exhibitors_structured.return_value = [
        ExhibitorSchema(name="Mock Exhibitor 1", relevance=7.0)
    ]
    
    mock_serper.search_communities.return_value = []

    # ── 2. Run Plan ──────────────────────────────────────────────────────────
    config = EventConfigInput(
        category="AI",
        geography="San Francisco",
        audience_size=500,
        budget_usd=25000.0,
        event_dates="2025-10-10",
        event_name="AI Test Summit"
    )
    
    # Set fake API key so check passes
    os.environ["OPENAI_API_KEY"] = "sk-mock"
    
    print(f"Invoking orchestrator for {config.event_name}...")
    try:
        final_state = await run_plan(config)
        
        print("\n--- Orchestration Success ---")
        print(f"Sponsors found: {len(final_state['sponsors'])}")
        print(f"Speakers found: {len(final_state['speakers'])}")
        print(f"Venues found: {len(final_state['venues'])}")
        print(f"Exhibitors found: {len(final_state['exhibitors'])}")
        print(f"Pricing tiers: {len(final_state['pricing'])}")
        print(f"Revenue projected: {final_state['revenue'].get('total_projected_revenue', 0)}")
        print(f"Schedule items: {len(final_state['schedule'])}")
        print(f"Errors: {final_state['errors']}")
        
        if final_state['errors']:
            for err in final_state['errors']:
                print(f"  - ERROR: {err}")
                
    except Exception as e:
        print(f"Orchestration failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
