
import os
import sys
from dotenv import load_dotenv

# Ensure we import from the local backend folder
sys.path.insert(0, os.path.abspath("."))

from backend.memory.vector_store import embed_and_store, similarity_search

def test_chroma():
    load_dotenv()
    
    # Verify environment
    or_key = os.getenv("OPENROUTER_API_KEY")
    print(f"OpenRouter Key present: {bool(or_key)}")
    print(f"Using OpenRouter Embeddings: {os.getenv('USE_OPENROUTER_EMBEDDINGS', 'true')}")
    print(f"Model: {os.getenv('EMBEDDING_MODEL', 'nvidia/llama-nemotron-embed-vl-1b-v2:free')}")
    
    test_collection = "test_chroma_fix_v4"
    test_docs = [
        "ConfMind is a multi-agent system for conference planning.",
        "The system uses LangGraph for orchestration.",
        "Agents include SponsorAgent, SpeakerAgent, and VenueAgent."
    ]
    test_meta = [
        {"source": "test", "id": 1},
        {"source": "test", "id": 2},
        {"source": "test", "id": 3}
    ]
    
    print("\n--- Testing embed_and_store ---")
    try:
        embed_and_store(test_docs, test_meta, collection=test_collection)
        print("SUCCESS: Documents stored without errors.")
    except Exception as e:
        print(f"FAILED: embed_and_store raised: {e}")
        return

    print("\n--- Testing similarity_search ---")
    try:
        query = "What is ConfMind?"
        results = similarity_search(query, collection=test_collection, k=2)
        print(f"SUCCESS: Found {len(results)} results.")
        for i, res in enumerate(results):
            print(f" Result {i+1}: {res['document'][:100]}... (Dist: {res.get('distance', 'N/A')})")
    except Exception as e:
        print(f"FAILED: similarity_search raised: {e}")

if __name__ == "__main__":
    test_chroma()
