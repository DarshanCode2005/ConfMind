"""
vector_store.py — ChromaDB (local dev) / Pinecone (prod) vector store wrapper.

Provides two public functions used by BaseAgent helpers:
    embed_and_store(docs, metadata, collection)  → None
    similarity_search(query, collection, k)      → list[dict]

Configuration
─────────────
Set USE_PINECONE=true in .env to switch from local ChromaDB to Pinecone.

Local dev (ChromaDB):   No extra setup; persists to ./chroma_db/ by default.
Production (Pinecone):  Requires PINECONE_API_KEY and PINECONE_ENV in .env.

Collection names used by agents
────────────────────────────────
"events"     → historical event records (used by Pricing + Revenue agents)
"sponsors"   → sponsor profiles discovered in past runs
"speakers"   → speaker profiles + past talk topics
"venues"     → venue data for semantic re-use across queries
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Moved inside functions to avoid early import overhead, but need types for class
import chromadb.utils.embedding_functions as embedding_functions

_USE_PINECONE = os.getenv("USE_PINECONE", "false").lower() == "true"
_CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")


class OpenRouterEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """Custom embedding function for OpenRouter to handle the free NVIDIA model."""

    def __init__(self, api_key: str, model_name: str):
        self._api_key = api_key
        self._model_name = model_name

    def __call__(self, input: list[str]) -> Any:
        import requests

        response = requests.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model_name,
                "input": input,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        embeddings = [item["embedding"] for item in data.get("data", [])]
        if not embeddings:
            raise ValueError(f"OpenRouter returned no embeddings for model {self._model_name}")
        return embeddings


def _get_chroma_collection(collection: str) -> Any:
    """Return (or create) a ChromaDB collection by name using local or API embeddings."""
    import chromadb  # type: ignore[import-untyped]
    from chromadb.utils import embedding_functions

    # Priority:
    # 1. OpenRouter (Free model suggested by user)
    # 2. OpenAI (Default, but may hit quota)
    # 3. Local (Fallback if keys are missing)

    or_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    # Use OpenRouter free model if available, else OpenAI
    if or_key and os.getenv("USE_OPENROUTER_EMBEDDINGS", "true").lower() == "true":
        model = os.getenv("EMBEDDING_MODEL", "nvidia/llama-nemotron-embed-vl-1b-v2:free")
        ef = OpenRouterEmbeddingFunction(api_key=or_key, model_name=model)
        # Suffix collection to avoid dimension mismatch with OpenAI 1536-dim vectors
        collection = f"{collection}_or"
    elif openai_key:
        ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=openai_key, model_name="text-embedding-3-small"
        )
    else:
        # Last resort fallback to local embeddings
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        collection = f"{collection}_local"

    client = chromadb.PersistentClient(path=_CHROMA_PERSIST_DIR)
    return client.get_or_create_collection(name=collection, embedding_function=ef)


def embed_and_store(
    docs: list[str],
    metadata: list[dict[str, Any]],
    collection: str = "events",
) -> None:
    """Embed documents and upsert them into the vector store.

    Each document is embedded using OpenAI text-embedding-3-small and stored
    alongside its metadata for later retrieval.

    Args:
        docs:       List of text strings to embed and store.
        metadata:   Parallel list of metadata dicts (same length as docs).
                    Each dict can contain any JSON-serialisable keys.
        collection: Target collection name (ChromaDB) or namespace (Pinecone).

    Raises:
        ValueError: If docs and metadata have different lengths.
        OSError:    If OPENAI_API_KEY is not set.

    Usage::

        embed_and_store(
            docs=["TechCorp sponsors AI events in Europe"],
            metadata=[{"name": "TechCorp", "tier": "Gold"}],
            collection="sponsors",
        )
    """
    if len(docs) != len(metadata):
        raise ValueError(
            f"docs ({len(docs)}) and metadata ({len(metadata)}) must have the same length"
        )
    if not docs:
        return

    if _USE_PINECONE:
        _pinecone_upsert(docs, metadata, collection)
    else:
        _chroma_upsert(docs, metadata, collection)


def similarity_search(
    query: str,
    collection: str = "events",
    k: int = 5,
    agents: list[str] | None = None,
) -> list[dict[str, Any]]:
    if _USE_PINECONE:
        return _pinecone_query(query, collection, k, agents)
    return _chroma_query(query, collection, k, agents)

def _chroma_query(query: str, collection: str, k: int, agents: list[str] | None = None) -> list[dict[str, Any]]:
    coll = _get_chroma_collection(collection)
    
    where = None
    if agents:
        if len(agents) == 1:
            where = {"agent": agents[0]}
        else:
            where = {"agent": {"$in": agents}}
            
    results = coll.query(
        query_texts=[query], n_results=k, include=["documents", "metadatas", "distances"], where=where
    )
    output: list[dict[str, Any]] = []
    
    # Handle empty results
    if not results.get("documents") or not results["documents"][0]:
        return output
        
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
        strict=False,
    ):
        output.append({"document": doc, "metadata": meta, "distance": dist})
    return output


def _chroma_upsert(
    docs: list[str],
    metadata: list[dict[str, Any]],
    collection: str,
) -> None:
    import hashlib

    coll = _get_chroma_collection(collection)
    
    # Generate stable IDs based on content to prevent duplicates
    ids = [hashlib.md5(doc.encode()).hexdigest() for doc in docs]
    
    coll.upsert(
        documents=docs,
        metadatas=metadata,
        ids=ids
    )


# ── Pinecone backend (production) ─────────────────────────────────────────────


def _get_pinecone_index(collection: str) -> Any:
    from pinecone import Pinecone  # type: ignore[import-untyped]

    api_key = os.getenv("PINECONE_API_KEY", "")
    if not api_key:
        raise OSError("PINECONE_API_KEY is not set — add it to your .env file.")
    pc = Pinecone(api_key=api_key)
    return pc.Index(collection)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts using OpenAI text-embedding-3-small."""
    from openai import OpenAI  # type: ignore[import-untyped]

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    response = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [item.embedding for item in response.data]


def _pinecone_upsert(
    docs: list[str],
    metadata: list[dict[str, Any]],
    collection: str,
) -> None:
    import hashlib

    index = _get_pinecone_index(collection)
    embeddings = _embed_texts(docs)
    vectors = [
        {
            "id": hashlib.md5(doc.encode()).hexdigest(),
            "values": emb,
            "metadata": {**meta, "_document": doc},
        }
        for doc, emb, meta in zip(docs, embeddings, metadata, strict=True)
    ]
    index.upsert(vectors=vectors)


def _pinecone_query(query: str, collection: str, k: int, agents: list[str] | None = None) -> list[dict[str, Any]]:
    index = _get_pinecone_index(collection)
    emb = _embed_texts([query])[0]
    
    filter = None
    if agents:
        if len(agents) == 1:
            filter = {"agent": {"$eq": agents[0]}}
        else:
            filter = {"agent": {"$in": agents}}
            
    res = index.query(vector=emb, top_k=k, include_metadata=True, filter=filter)
    return [
        {
            "document": match["metadata"].pop("_document", ""),
            "metadata": match["metadata"],
            "distance": 1.0 - match["score"],  # convert similarity to distance
        }
        for match in res["matches"]
    ]
