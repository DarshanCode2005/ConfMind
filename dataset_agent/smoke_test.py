"""smoke_test.py - quick validation of dataset_agent tools and model"""
import sys
sys.path.insert(0, r"c:/coding vs/tech_gc/ConfMind")

from dataset_agent.tools import web_search

results = web_search("NeurIPS 2025 conference", 3)
print(f"web_search: Got {len(results)} results")
for r in results:
    print(f"  - {r.get('title', 'no title')}")

import ollama
resp = ollama.chat(
    model="confmind-gemma4",
    messages=[{"role": "user", "content": "Reply with only: OK"}],
)
print(f"model response: {resp['message']['content'].strip()}")
