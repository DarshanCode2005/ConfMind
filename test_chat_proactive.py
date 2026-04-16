import asyncio
import os
import uuid
import sys
from dotenv import load_dotenv

load_dotenv()

# Ensure backend imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.agents.chat_agent import chat_agent_host, generate_workflow_completion_summary, get_chat_state

async def test():
    plan_id = str(uuid.uuid4())
    
    # Mocking a basic plan output state
    plan_data = {
        "event_config": {"event_name": "AI Builders Summit", "category": "AI", "geography": "USA"},
        "venues": [{"name": "Grand Hall Convention Center"}, {"name": "Skyline Ballroom"}],
        "speakers": [{"name": "Dr. Jane Smith"}, {"name": "Prof. Alan Turing"}],
        "sponsors": [{"name": "TechCorp"}, {"name": "Future Systems"}],
        "revenue": {"total_projected_revenue": 150000.0}
    }
    
    print("--- Simulating workflow completion ---")
    await generate_workflow_completion_summary(plan_id, plan_data)
    
    chat_state = get_chat_state(plan_id)
    print("Initial Proactive message stored in chat_history:")
    for msg in chat_state["chat_history"]:
        print(f"[{msg['role']}]: {msg['content']}\n")
        
    print("--- Simulating user joining the chat ---")
    user_msg = "I don't like the speakers. Can you rerun the speaker agent?"
    print(f"[user]: {user_msg}\n")
    
    # Send message to chat agent
    response = await chat_agent_host.invoke(session_id=plan_id, message=user_msg, plan_id=plan_id)
    print(f"\n[assistant]: {response}\n")
    
    print("--- Post-interaction Chat State ---")
    print(f"Pending rerun triggers: {chat_state['pending_rerun']}")
    print(f"Current Summary: {chat_state['current_summary']}")

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Please set OPENAI_API_KEY. It is missing in the environment.")
    else:
        asyncio.run(test())
