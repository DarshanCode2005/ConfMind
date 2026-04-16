import asyncio
import os
import unittest
from unittest.mock import patch, MagicMock

# Force Ollama for testing
os.environ["USE_OLLAMA"] = "true"
os.environ["OLLAMA_MODEL"] = "gemma4"
os.environ["OPENAI_API_KEY"] = ""  # Disable OpenAI
os.environ["GEMINI_API_KEY"] = ""  # Disable Gemini
os.environ["OPENROUTER_API_KEY"] = ""  # Disable OpenRouter

from backend.agents.chat_agent import ChatAgentHost

async def test_email_drafting_ollama():
    print("\n--- Testing Email Drafting with Local Ollama (gemma4) ---")
    host = ChatAgentHost()
    
    session_id = "test_persistence_id"
    
    # Mock search results
    mock_rag_results = [
        {"document": "TechCorp is a leading AI cloud provider based in Berlin.", "metadata": {"name": "TechCorp", "category": "sponsor"}}
    ]
    mock_contact_info = "Email: partnerships@techcorp.com\nWebsite: techcorp.com/events"
    
    with patch("backend.agents.chat_agent.similarity_search", return_value=mock_rag_results):
        with patch("backend.agents.chat_agent.find_contact_info", return_value=mock_contact_info):
            # We also need to mock create_react_agent or at least ensure it uses our mocked tools
            # Since create_react_agent is complex, we'll let it run but it might be slow on local gemma4
            print("Sending outreach request...")
            response = await host.invoke(
                session_id=session_id,
                message="Send mail to TechCorp sponsor"
            )
            
            print(f"\n[AGENT RESPONSE]\n{response}\n")
            
            # Check persistence
            print("Checking persistence (asking follow-up)...")
            follow_up = await host.invoke(
                session_id=session_id,
                message="What was the name of that sponsor again?"
            )
            print(f"\n[FOLLOW-UP RESPONSE]\n{follow_up}\n")

if __name__ == "__main__":
    asyncio.run(test_email_drafting_ollama())
