import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Set up paths
root_dir = Path(__file__).parent.parent.resolve()
sys.path.append(str(root_dir))
sys.path.append(str(root_dir / "backend"))

load_dotenv(root_dir / ".env")

from backend.orchestrator import run_plan
from backend.models.schemas import EventConfigInput

async def test_full_pipeline():
    print("="*60)
    print("      CONFMIND 2026 SPEC - FULL INTEGRATION TEST")
    print("="*60)
    
    # 1. Provide configuration exactly as the new architecture expects.
    # Note: For faster testing we use a small audience size which affects ops/pricing.
    config = EventConfigInput(
        category="Tech Conferences",
        geography="San Francisco, CA",
        audience_size=300,
        budget_usd=100000.0,
        event_dates="2025-10-10",
        event_name="Future AI Tech Summit"
    )

    print(f"\n[ORCHESTRATOR] Starting plan for: {config.event_name}")
    print(f"[LANGSMITH] Setting LANGCHAIN_PROJECT={os.getenv('LANGCHAIN_PROJECT', 'confmind-backend')}")
    print(f"[LANGSMITH] Tracing Enabled: {os.getenv('LANGCHAIN_TRACING_V2', 'false')}")
    print("-" * 60)

    try:
        # Run the full orchestrated LangGraph
        # This will trigger N WebSearch agents -> Memory -> Sub-agents
        final_state = await run_plan(config)

        print("\n" + "="*60)
        print("             FINAL PLAN SUMMARY (2026 SPEC)")
        print("="*60)
        
        # Verify past_events ingestion
        past_events = final_state.get('past_events', [])
        print(f"\n[DATA PIPELINE] Ingested {len(past_events)} past events via PredictHQ/Tavily.")
        
        # Determine the number of dynamically spawned agents based on past events
        # Web search agents are N spawned agents in parallel.
        
        # Verify specialized agent outputs
        print(f"[SPONSORS] Ranked {len(final_state.get('sponsors', []))} sponsors.")
        print(f"[SPEAKERS] Scaled {len(final_state.get('speakers', []))} influential speakers.")
        print(f"[VENUES] Found {len(final_state.get('venues', []))} venues.")
        print(f"[EXHIBITORS] Clustered {len(final_state.get('exhibitors', []))} exhibitors.")
        print(f"[PRICING] Derived {len(final_state.get('pricing', []))} pricing tiers.")
        print(f"[COMMUNITIES] Discovered {len(final_state.get('communities', []))} communities.")
        print(f"[OPS] Generated {len(final_state.get('schedule', []))} schedule entries.")
        
        # Verify financial aggregates
        rev = final_state.get('revenue', {})
        print(f"\n[FINANCIALS]")
        print(f"  - Total Projected Revenue: ${rev.get('total_projected_revenue', 0):,.2f}")
        print(f"  - Projected Profit: ${rev.get('projected_profit', 0):,.2f}")
        print(f"  - Break Even Attendees: {rev.get('break_even', {}).get('attendance_needed', 0)}")
        
        if final_state.get('errors'):
            print("\n" + "!"*60)
            print("                ERRORS ENCOUNTERED")
            print("!"*60)
            for err in final_state['errors']:
                print(f"  [!] {err}")
        else:
            print("\n[SUCCESS] Pipeline executed with zero hard failures.")

    except Exception as e:
        print(f"\n[FATAL ERROR] Orchestration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("[SYSTEM] Executing full integration test. This may take several minutes as it hits real LLMs and APIs.")
    asyncio.run(test_full_pipeline())
