"""
tavily_tool.py — Search the web via Tavily API.

Tavily is optimized for LLMs and returns clean text content / snippets.
It is specifically used here for finding contact information and email addresses
for sponsors and speakers.

Environment variables
─────────────────────
TAVILY_API_KEY   Required. Get a key at https://tavily.com
"""

from __future__ import annotations

import os
from typing import Any

from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

def get_tavily_client() -> TavilyClient:
    """Initialize Tavily client with API key."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise OSError("TAVILY_API_KEY is not set. Add it to your .env file.")
    return TavilyClient(api_key=api_key)

async def search_tavily(query: str, search_depth: str = "smart") -> str:
    """
    Search the web using Tavily.
    
    Args:
        query: The search query.
        search_depth: 'basic' or 'smart'.
        
    Returns:
        A concatenated string of the most relevant search results.
    """
    client = get_tavily_client()
    try:
        # tavily-python is synchronous, but we wrap it in a helper if needed.
        # For now, we use the simple search.
        response = client.search(query=query, search_depth=search_depth)
        
        results = []
        for result in response.get("results", []):
            results.append(f"Source: {result.get('url')}\nContent: {result.get('content')}")
            
        return "\n\n---\n\n".join(results)
    except Exception as e:
        return f"Search failed: {e}"

def find_contact_info(name: str, org_type: str = "sponsor") -> str:
    """
    Specifically try to find email or contact page for a person/organization.
    """
    client = get_tavily_client()
    query = f"contact email or official website for {name} {org_type}"
    try:
        response = client.search(query=query, search_depth="smart")
        results = []
        for result in response.get("results", []):
            results.append(f"URL: {result.get('url')}\nSnippet: {result.get('content')}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Failed to find contact info: {e}"
