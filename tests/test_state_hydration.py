
import pytest
from backend.models.schemas import EventConfigInput, SponsorSchema
from backend.orchestrator import hydrate_state, rerun_nodes
from unittest.mock import MagicMock, patch

def test_hydrate_state_converts_dicts_to_models():
    raw_state = {
        "event_config": {
            "category": "AI",
            "geography": "Europe",
            "audience_size": 800,
            "budget_usd": 50000,
            "event_dates": "2025-09-15"
        },
        "sponsors": [
            {"name": "Google", "tier": "Gold", "relevance_score": 9.5}
        ]
    }
    
    hydrated = hydrate_state(raw_state)
    
    assert isinstance(hydrated["event_config"], EventConfigInput)
    assert hydrated["event_config"].category == "AI"
    assert isinstance(hydrated["sponsors"][0], SponsorSchema)
    assert hydrated["sponsors"][0].name == "Google"

@pytest.mark.asyncio
async def test_rerun_nodes_hydrates_automatically():
    raw_state = {
        "event_config": {
            "category": "AI",
            "geography": "Europe",
            "audience_size": 800,
            "budget_usd": 50000,
            "event_dates": "2025-09-15"
        }
    }
    
    class MockAgent:
        name = "test_agent"
        def run(self, state):
            # If this is called, hydration should have happened
            assert isinstance(state["event_config"], EventConfigInput)
            return {"metadata": {"tested": True}}

    with patch("backend.orchestrator._import_agents") as mock_import:
        mock_import.return_value = {"test_agent": MockAgent()}
        
        result = await rerun_nodes(["test_agent"], raw_state)
        assert result["metadata"]["tested"] is True
